from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import (
    Customer,
    DeploymentTask,
    Domain,
    PaymentOrder,
    ReminderLog,
    ReminderTemplate,
    Server,
)
from app.schemas.public import CustomerConfigResponse
from app.schemas.summary import AdminSummaryResponse, ExpiringResourceItem

DEFAULT_REMINDER_TEMPLATES: tuple[tuple[str, int, str], ...] = (
    (
        "7天提醒",
        7,
        "尊敬的{name}，您的服务将于 {expires_on} 到期，当前还剩 {days_left} 天。"
        "服务器 IP：{server_ip}，域名：{domain_name}。请提前安排续费。",
    ),
    (
        "3天提醒",
        3,
        "尊敬的{name}，您的服务将在 {days_left} 天后到期（到期日：{expires_on}）。"
        "服务器 IP：{server_ip}，域名：{domain_name}。请尽快处理续费。",
    ),
    (
        "1天提醒",
        1,
        "尊敬的{name}，您的服务明天到期（{expires_on}）。"
        "服务器 IP：{server_ip}，域名：{domain_name}。请及时续费避免中断。",
    ),
    (
        "到期通知",
        0,
        "尊敬的{name}，您的服务今天已到期（{expires_on}）。"
        "服务器 IP：{server_ip}，域名：{domain_name}。如需继续使用，请立即续费。",
    ),
)


@dataclass(slots=True)
class CustomerServiceInfo:
    customer: Customer
    expires_on: date | None
    days_left: int | None
    server_ip: str | None
    domain_name: str | None


@dataclass(slots=True)
class ReminderDispatch:
    customer: Customer
    template: ReminderTemplate
    days_left: int
    message: str


def build_customer_code(name: str) -> str:
    ascii_like = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    if ascii_like:
        return ascii_like[:40]
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"cust-{digest}"


def validate_customer_name(customer_name: str) -> str:
    normalized_name = customer_name.strip()
    if not normalized_name:
        raise ValueError("客户名不能为空。")
    return normalized_name


def validate_server_host(server_host: str) -> str:
    normalized_host = server_host.strip()
    try:
        return str(ipaddress.ip_address(normalized_host))
    except ValueError as exc:
        raise ValueError("服务器 IP 格式错误，请使用合法的 IPv4 或 IPv6 地址。") from exc


def validate_domain_name(domain_name: str) -> str:
    normalized_domain = domain_name.lower().strip().rstrip(".")
    if len(normalized_domain) > 253:
        raise ValueError("域名格式错误，请输入合法域名。")

    labels = normalized_domain.split(".")
    if len(labels) < 2:
        raise ValueError("域名格式错误，请输入合法域名。")

    label_pattern = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    if any(not label_pattern.fullmatch(label) for label in labels):
        raise ValueError("域名格式错误，请输入合法域名。")

    return normalized_domain


def parse_expires_on(expires_text: str) -> date:
    try:
        return datetime.strptime(expires_text.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("到期日期格式错误，请使用 YYYY-MM-DD。") from exc


def compute_days_left(expires_on: date | None, today: date | None = None) -> int | None:
    if expires_on is None:
        return None
    base_day = today or date.today()
    return (expires_on - base_day).days


def build_customer_service_info(customer: Customer, today: date | None = None) -> CustomerServiceInfo:
    server = customer.servers[0] if customer.servers else None
    domain = customer.domains[0] if customer.domains else None
    expires_on = customer.expires_on or (
        domain.expires_on if domain and domain.expires_on else server.expires_on if server else None
    )
    server_ip = customer.server_ip or (server.host if server else None)
    domain_name = customer.domain_name or (domain.domain if domain else None)
    return CustomerServiceInfo(
        customer=customer,
        expires_on=expires_on,
        days_left=compute_days_left(expires_on, today=today),
        server_ip=server_ip,
        domain_name=domain_name,
    )


async def ensure_customer_bundle(
    session: AsyncSession,
    customer_name: str,
    server_host: str,
    domain_name: str,
    expires_on: date,
    telegram_id: str | None = None,
    note: str | None = None,
) -> Customer:
    normalized_name = validate_customer_name(customer_name)
    normalized_host = validate_server_host(server_host)
    normalized_domain = validate_domain_name(domain_name)
    normalized_telegram_id = telegram_id.strip() if telegram_id else None

    existing_customer = await session.scalar(select(Customer).where(Customer.name == normalized_name))
    if existing_customer is not None:
        raise ValueError("该客户已存在，请使用 /update 更新信息。")

    if normalized_telegram_id:
        duplicate_telegram = await session.scalar(
            select(Customer).where(Customer.telegram_id == normalized_telegram_id)
        )
        if duplicate_telegram is not None:
            raise ValueError("该 Telegram 账号已绑定到其他客户。")

    duplicate_resource = await session.execute(
        select(Server.host, Domain.domain)
        .select_from(Customer)
        .outerjoin(Server, Server.customer_id == Customer.id)
        .outerjoin(Domain, Domain.customer_id == Customer.id)
        .where(or_(Server.host == normalized_host, Domain.domain == normalized_domain))
    )
    if duplicate_resource.first() is not None:
        existing_server = await session.scalar(select(Server).where(Server.host == normalized_host))
        if existing_server is not None:
            raise ValueError("该服务器 IP 已绑定到其他客户，不能重复录入。")
        raise ValueError("该域名已绑定到其他客户，不能重复录入。")

    customer = Customer(
        code=build_customer_code(normalized_name),
        name=normalized_name,
        telegram_id=normalized_telegram_id,
        server_ip=normalized_host,
        domain_name=normalized_domain,
        expires_on=expires_on,
        brand_name=normalized_name,
        support_text="请联系管理员处理续费与配置。",
        note=note,
        notes=note,
    )
    session.add(customer)
    await session.flush()

    session.add(
        Server(
            customer_id=customer.id,
            name=f"{normalized_name}-server",
            host=normalized_host,
            ssh_port=settings.deploy_default_ssh_port,
            ssh_user=settings.deploy_default_ssh_user,
            expires_on=expires_on,
            region="ap-southeast-1",
        )
    )
    session.add(
        Domain(
            customer_id=customer.id,
            domain=normalized_domain,
            zone_name=normalized_domain,
            expires_on=expires_on,
        )
    )

    await session.commit()
    return await get_customer_by_keyword(session, normalized_name, eager=True) or customer


async def get_customer_by_keyword(
    session: AsyncSession, keyword: str, eager: bool = False
) -> Customer | None:
    normalized = keyword.strip()
    stmt = select(Customer).where((Customer.name == normalized) | (Customer.code == normalized))
    if eager:
        stmt = stmt.options(selectinload(Customer.domains), selectinload(Customer.servers))
    return await session.scalar(stmt)


async def get_customer_by_telegram_id(session: AsyncSession, telegram_id: str) -> Customer | None:
    return await session.scalar(
        select(Customer)
        .options(selectinload(Customer.domains), selectinload(Customer.servers))
        .where(Customer.telegram_id == telegram_id.strip())
    )


async def list_customers(session: AsyncSession) -> list[Customer]:
    return list(
        (
            await session.scalars(
                select(Customer)
                .options(selectinload(Customer.domains), selectinload(Customer.servers))
                .order_by(Customer.created_at.asc(), Customer.name.asc())
            )
        ).all()
    )


async def update_customer_bundle(
    session: AsyncSession,
    customer_keyword: str,
    server_host: str,
    domain_name: str,
    expires_on: date,
    telegram_id: str | None = None,
    note: str | None = None,
) -> Customer:
    normalized_host = validate_server_host(server_host)
    normalized_domain = validate_domain_name(domain_name)
    normalized_telegram_id = telegram_id.strip() if telegram_id else None

    customer = await session.scalar(
        select(Customer)
        .options(selectinload(Customer.domains), selectinload(Customer.servers))
        .where((Customer.name == customer_keyword.strip()) | (Customer.code == customer_keyword.strip()))
    )
    if customer is None:
        raise ValueError("未找到对应客户。")

    existing_server = await session.scalar(select(Server).where(Server.host == normalized_host))
    if existing_server is not None and existing_server.customer_id != customer.id:
        raise ValueError("该服务器 IP 已绑定到其他客户，不能重复录入。")

    existing_domain = await session.scalar(select(Domain).where(Domain.domain == normalized_domain))
    if existing_domain is not None and existing_domain.customer_id != customer.id:
        raise ValueError("该域名已绑定到其他客户，不能重复录入。")

    if normalized_telegram_id:
        existing_customer = await session.scalar(select(Customer).where(Customer.telegram_id == normalized_telegram_id))
        if existing_customer is not None and existing_customer.id != customer.id:
            raise ValueError("该 Telegram 账号已绑定到其他客户。")

    server = customer.servers[0] if customer.servers else None
    domain = customer.domains[0] if customer.domains else None

    if server is None:
        session.add(
            Server(
                customer_id=customer.id,
                name=f"{customer.name}-server",
                host=normalized_host,
                ssh_port=settings.deploy_default_ssh_port,
                ssh_user=settings.deploy_default_ssh_user,
                expires_on=expires_on,
                region="ap-southeast-1",
            )
        )
    else:
        server.host = normalized_host
        server.expires_on = expires_on

    if domain is None:
        session.add(
            Domain(
                customer_id=customer.id,
                domain=normalized_domain,
                zone_name=normalized_domain,
                expires_on=expires_on,
            )
        )
    else:
        domain.domain = normalized_domain
        domain.zone_name = normalized_domain
        domain.expires_on = expires_on

    customer.server_ip = normalized_host
    customer.domain_name = normalized_domain
    customer.expires_on = expires_on
    customer.telegram_id = normalized_telegram_id or customer.telegram_id
    if note is not None:
        customer.note = note
        customer.notes = note

    await session.commit()
    return await get_customer_by_keyword(session, customer_keyword, eager=True) or customer


async def delete_customer_bundle(session: AsyncSession, customer_keyword: str) -> Customer:
    customer = await get_customer_by_keyword(session, customer_keyword)
    if customer is None:
        raise ValueError("未找到对应客户。")

    await session.delete(customer)
    await session.commit()
    return customer


async def count_customer_related_records(session: AsyncSession, customer_id: str) -> dict[str, int]:
    domain_count = await session.scalar(
        select(func.count()).select_from(Domain).where(Domain.customer_id == customer_id)
    ) or 0
    server_count = await session.scalar(
        select(func.count()).select_from(Server).where(Server.customer_id == customer_id)
    ) or 0
    payment_count = await session.scalar(
        select(func.count()).select_from(PaymentOrder).where(PaymentOrder.customer_id == customer_id)
    ) or 0
    deployment_count = await session.scalar(
        select(func.count()).select_from(DeploymentTask).where(DeploymentTask.customer_id == customer_id)
    ) or 0
    return {
        "domains": domain_count,
        "servers": server_count,
        "payment_orders": payment_count,
        "deployment_tasks": deployment_count,
    }


async def get_customer_config(session: AsyncSession, keyword: str) -> CustomerConfigResponse | None:
    customer = await get_customer_by_keyword(session, keyword)
    if customer is None:
        return None

    return CustomerConfigResponse(
        customer_code=customer.code,
        customer_name=customer.name,
        brand_name=customer.brand_name or customer.name,
        logo_url=customer.logo_url,
        theme_primary=customer.theme_primary,
        theme_secondary=customer.theme_secondary,
        support_text=customer.support_text,
    )


async def build_admin_summary(session: AsyncSession) -> AdminSummaryResponse:
    today = date.today()
    upcoming = today + timedelta(days=7)

    total_customers = await session.scalar(select(func.count()).select_from(Customer)) or 0
    total_domains = await session.scalar(select(func.count()).select_from(Domain)) or 0
    total_servers = await session.scalar(select(func.count()).select_from(Server)) or 0
    pending_payments = await session.scalar(
        select(func.count()).select_from(PaymentOrder).where(PaymentOrder.status.in_(["pending", "checking"]))
    ) or 0
    queued_deployments = await session.scalar(
        select(func.count()).select_from(DeploymentTask).where(
            DeploymentTask.status.in_(["queued", "running"])
        )
    ) or 0

    expiring_resources: list[ExpiringResourceItem] = []

    domains = (
        await session.scalars(
            select(Domain)
            .options(selectinload(Domain.customer))
            .where(Domain.expires_on.is_not(None), Domain.status == "active", Domain.expires_on <= upcoming)
            .order_by(Domain.expires_on.asc())
            .limit(10)
        )
    ).all()

    servers = (
        await session.scalars(
            select(Server)
            .options(selectinload(Server.customer))
            .where(Server.expires_on.is_not(None), Server.status == "active", Server.expires_on <= upcoming)
            .order_by(Server.expires_on.asc())
            .limit(10)
        )
    ).all()

    for domain in domains:
        if domain.expires_on is None:
            continue
        expiring_resources.append(
            ExpiringResourceItem(
                resource_type="域名",
                customer_name=domain.customer.name,
                identifier=domain.domain,
                expires_on=domain.expires_on,
                days_left=(domain.expires_on - today).days,
            )
        )

    for server in servers:
        if server.expires_on is None:
            continue
        expiring_resources.append(
            ExpiringResourceItem(
                resource_type="服务器",
                customer_name=server.customer.name,
                identifier=server.host,
                expires_on=server.expires_on,
                days_left=(server.expires_on - today).days,
            )
        )

    expiring_resources.sort(key=lambda item: (item.days_left, item.resource_type, item.customer_name))

    return AdminSummaryResponse(
        total_customers=total_customers,
        total_domains=total_domains,
        total_servers=total_servers,
        pending_payments=pending_payments,
        queued_deployments=queued_deployments,
        expiring_resources=expiring_resources[:12],
    )


async def seed_default_reminder_templates(session: AsyncSession) -> list[ReminderTemplate]:
    templates: list[ReminderTemplate] = []
    for name, days_before, template in DEFAULT_REMINDER_TEMPLATES:
        existing = await session.scalar(select(ReminderTemplate).where(ReminderTemplate.name == name))
        if existing is not None:
            templates.append(existing)
            continue

        record = ReminderTemplate(name=name, days_before=days_before, template=template, is_active=True)
        session.add(record)
        templates.append(record)

    await session.commit()
    return list(
        (
            await session.scalars(
                select(ReminderTemplate).where(ReminderTemplate.is_active.is_(True)).order_by(ReminderTemplate.days_before.desc())
            )
        ).all()
    )


async def seed_test_customers(session: AsyncSession, today: date | None = None) -> list[Customer]:
    base_day = today or date.today()
    fixtures = (
        ("客户A", "10.0.0.7", "customer-a.example.com", 7, "10001"),
        ("客户B", "10.0.0.3", "customer-b.example.com", 3, "10002"),
        ("客户C", "10.0.0.1", "customer-c.example.com", 1, "10003"),
        ("客户D", "10.0.0.9", "customer-d.example.com", 0, "10004"),
    )
    customers: list[Customer] = []
    for name, server_ip, domain_name, offset, telegram_id in fixtures:
        existing = await session.scalar(select(Customer).where(Customer.name == name))
        if existing is None:
            customer = await ensure_customer_bundle(
                session=session,
                customer_name=name,
                server_host=server_ip,
                domain_name=domain_name,
                expires_on=base_day + timedelta(days=offset),
                telegram_id=telegram_id,
                note="TASK_001 测试数据",
            )
        else:
            customer = await update_customer_bundle(
                session=session,
                customer_keyword=name,
                server_host=server_ip,
                domain_name=domain_name,
                expires_on=base_day + timedelta(days=offset),
                telegram_id=telegram_id,
                note="TASK_001 测试数据",
            )
        customers.append(customer)
    return customers


async def build_my_service_text(session: AsyncSession, telegram_id: str, today: date | None = None) -> str | None:
    customer = await get_customer_by_telegram_id(session, telegram_id)
    if customer is None:
        return None

    info = build_customer_service_info(customer, today=today)
    days_left_text = "未设置"
    if info.days_left is not None:
        if info.days_left > 0:
            days_left_text = f"{info.days_left} 天"
        elif info.days_left == 0:
            days_left_text = "今天到期"
        else:
            days_left_text = f"已过期 {abs(info.days_left)} 天"

    return "\n".join(
        [
            f"客户：{customer.name}",
            f"状态：{customer.status}",
            f"到期时间：{info.expires_on.isoformat() if info.expires_on else '-'}",
            f"剩余时间：{days_left_text}",
            f"服务器 IP：{info.server_ip or '-'}",
            f"域名：{info.domain_name or '-'}",
            f"备注：{customer.note or customer.notes or '-'}",
        ]
    )


def render_reminder_message(customer: Customer, template: ReminderTemplate, today: date | None = None) -> str:
    info = build_customer_service_info(customer, today=today)
    return template.template.format(
        name=customer.name,
        days_left=info.days_left if info.days_left is not None else "-",
        expires_on=info.expires_on.isoformat() if info.expires_on else "-",
        server_ip=info.server_ip or "-",
        domain_name=info.domain_name or "-",
    )


async def has_sent_reminder_today(
    session: AsyncSession, customer_id: str, days_before: int, today: date | None = None
) -> bool:
    base_day = today or date.today()
    count = await session.scalar(
        select(func.count())
        .select_from(ReminderLog)
        .where(
            ReminderLog.customer_id == customer_id,
            ReminderLog.days_before == days_before,
            func.date(ReminderLog.sent_at) == base_day.isoformat(),
        )
    )
    return bool(count)


async def collect_due_reminders(
    session: AsyncSession, today: date | None = None
) -> list[ReminderDispatch]:
    base_day = today or date.today()
    templates = (
        await session.scalars(
            select(ReminderTemplate)
            .where(ReminderTemplate.is_active.is_(True))
            .order_by(ReminderTemplate.days_before.desc())
        )
    ).all()
    if not templates:
        await seed_default_reminder_templates(session)
        templates = (
            await session.scalars(
                select(ReminderTemplate)
                .where(ReminderTemplate.is_active.is_(True))
                .order_by(ReminderTemplate.days_before.desc())
            )
        ).all()

    trigger_days = [template.days_before for template in templates]
    customers = (
        await session.scalars(
            select(Customer)
            .options(selectinload(Customer.domains), selectinload(Customer.servers))
            .where(Customer.expires_on.is_not(None), Customer.status == "active")
        )
    ).all()

    due_items: list[ReminderDispatch] = []
    template_map = {template.days_before: template for template in templates}

    for customer in customers:
        info = build_customer_service_info(customer, today=base_day)
        if info.days_left is None or info.days_left not in trigger_days:
            continue
        if await has_sent_reminder_today(session, customer.id, info.days_left, today=base_day):
            continue

        template = template_map[info.days_left]
        due_items.append(
            ReminderDispatch(
                customer=customer,
                template=template,
                days_left=info.days_left,
                message=render_reminder_message(customer, template, today=base_day),
            )
        )

    due_items.sort(key=lambda item: (item.days_left, item.customer.name))
    return due_items


async def log_reminder_sent(
    session: AsyncSession, customer: Customer, days_before: int, message: str, status: str = "sent"
) -> ReminderLog:
    log = ReminderLog(customer_id=customer.id, days_before=days_before, status=status, message=message)
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log
