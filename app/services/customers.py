from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta

from sqlalchemy import func, select
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


async def ensure_customer_bundle(
    session: AsyncSession,
    customer_name: str,
    server_host: str,
    domain_name: str,
    expires_on: date,
) -> Customer:
    normalized_domain = domain_name.lower().strip()
    existing_customer = await session.scalar(select(Customer).where(Customer.name == customer_name))
    if existing_customer is None:
        existing_customer = Customer(
            code=build_customer_code(customer_name),
            name=customer_name,
            brand_name=customer_name,
            support_text="请联系管理员处理续费与配置。",
        )
        session.add(existing_customer)
        await session.flush()

    existing_server = await session.scalar(select(Server).where(Server.host == server_host))
    if existing_server is None:
        session.add(
            Server(
                customer_id=existing_customer.id,
                name=f"{customer_name}-server",
                host=server_host,
                ssh_port=settings.deploy_default_ssh_port,
                ssh_user=settings.deploy_default_ssh_user,
                expires_on=expires_on,
                region="ap-southeast-1",
            )
        )
    elif existing_server.customer_id != existing_customer.id:
        raise ValueError("该服务器 IP 已绑定到其他客户，不能重复录入。")
    else:
        existing_server.expires_on = expires_on

    existing_domain = await session.scalar(select(Domain).where(Domain.domain == normalized_domain))
    if existing_domain is None:
        session.add(
            Domain(
                customer_id=existing_customer.id,
                domain=normalized_domain,
                zone_name=normalized_domain,
                expires_on=expires_on,
            )
        )
    elif existing_domain.customer_id != existing_customer.id:
        raise ValueError("该域名已绑定到其他客户，不能重复录入。")
    else:
        existing_domain.expires_on = expires_on

    await session.commit()
    await session.refresh(existing_customer)
    return existing_customer


async def get_customer_by_keyword(session: AsyncSession, keyword: str) -> Customer | None:
    normalized = keyword.strip()
    return await session.scalar(
        select(Customer).where((Customer.name == normalized) | (Customer.code == normalized))
    )


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

