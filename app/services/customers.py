from __future__ import annotations

import hashlib
import ipaddress
import re
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import Customer, DeploymentTask, Domain, PaymentOrder, Server
from app.schemas.public import CustomerConfigResponse
from app.schemas.summary import AdminSummaryResponse, ExpiringResourceItem


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


async def ensure_customer_bundle(
    session: AsyncSession,
    customer_name: str,
    server_host: str,
    domain_name: str,
    expires_on: date,
) -> Customer:
    normalized_name = validate_customer_name(customer_name)
    normalized_host = validate_server_host(server_host)
    normalized_domain = validate_domain_name(domain_name)

    existing_customer = await session.scalar(select(Customer).where(Customer.name == normalized_name))
    if existing_customer is not None:
        raise ValueError("该客户已存在，请使用 /update 更新信息。")

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
        brand_name=normalized_name,
        support_text="请联系管理员处理续费与配置。",
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
    await session.refresh(customer)
    return customer


async def get_customer_by_keyword(session: AsyncSession, keyword: str) -> Customer | None:
    normalized = keyword.strip()
    return await session.scalar(
        select(Customer).where((Customer.name == normalized) | (Customer.code == normalized))
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
) -> Customer:
    normalized_host = validate_server_host(server_host)
    normalized_domain = validate_domain_name(domain_name)

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

    await session.commit()
    await session.refresh(customer)
    return customer


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
