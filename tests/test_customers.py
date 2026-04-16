from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Customer, DeploymentTask, Domain, PaymentOrder, ReminderLog, ReminderTemplate, Server
from app.services.customers import (
    build_my_service_text,
    collect_due_reminders,
    delete_customer_bundle,
    ensure_customer_bundle,
    list_customers,
    log_reminder_sent,
    parse_expires_on,
    seed_default_reminder_templates,
    seed_test_customers,
    update_customer_bundle,
    validate_domain_name,
    validate_server_host,
)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db

    await engine.dispose()


@pytest.mark.asyncio
async def test_add_customer_and_list(session: AsyncSession) -> None:
    customer = await ensure_customer_bundle(
        session=session,
        customer_name="客户A",
        server_host="1.1.1.1",
        domain_name="Example.COM",
        expires_on=date(2027, 1, 1),
        telegram_id="10086",
    )

    customers = await list_customers(session)

    assert customer.name == "客户A"
    assert customer.telegram_id == "10086"
    assert len(customers) == 1
    assert customers[0].servers[0].host == "1.1.1.1"
    assert customers[0].domains[0].domain == "example.com"
    assert customers[0].server_ip == "1.1.1.1"
    assert customers[0].domain_name == "example.com"
    assert customers[0].expires_on == date(2027, 1, 1)


@pytest.mark.asyncio
async def test_add_customer_rejects_duplicate_customer(session: AsyncSession) -> None:
    await ensure_customer_bundle(
        session=session,
        customer_name="客户A",
        server_host="1.1.1.1",
        domain_name="example.com",
        expires_on=date(2027, 1, 1),
    )

    with pytest.raises(ValueError, match="该客户已存在"):
        await ensure_customer_bundle(
            session=session,
            customer_name="客户A",
            server_host="2.2.2.2",
            domain_name="example.net",
            expires_on=date(2027, 2, 1),
        )


@pytest.mark.asyncio
async def test_update_customer_bundle(session: AsyncSession) -> None:
    await ensure_customer_bundle(
        session=session,
        customer_name="客户A",
        server_host="1.1.1.1",
        domain_name="example.com",
        expires_on=date(2027, 1, 1),
    )

    customer = await update_customer_bundle(
        session=session,
        customer_keyword="客户A",
        server_host="2.2.2.2",
        domain_name="new-example.com",
        expires_on=date(2028, 3, 4),
        telegram_id="20001",
    )

    assert customer.name == "客户A"

    refreshed_customer = await session.scalar(
        select(Customer).where(Customer.name == "客户A")
    )
    refreshed_server = await session.scalar(
        select(Server).where(Server.customer_id == refreshed_customer.id)
    )
    refreshed_domain = await session.scalar(
        select(Domain).where(Domain.customer_id == refreshed_customer.id)
    )
    assert refreshed_server.host == "2.2.2.2"
    assert refreshed_domain.domain == "new-example.com"
    assert refreshed_domain.expires_on == date(2028, 3, 4)
    assert customer.telegram_id == "20001"


@pytest.mark.asyncio
async def test_build_my_service_text_uses_telegram_binding(session: AsyncSession) -> None:
    await ensure_customer_bundle(
        session=session,
        customer_name="客户A",
        server_host="1.1.1.1",
        domain_name="example.com",
        expires_on=date(2027, 1, 8),
        telegram_id="30001",
        note="测试备注",
    )

    message = await build_my_service_text(session, "30001", today=date(2027, 1, 1))

    assert message is not None
    assert "客户：客户A" in message
    assert "剩余时间：7 天" in message
    assert "服务器 IP：1.1.1.1" in message
    assert "域名：example.com" in message
    assert "备注：测试备注" in message


@pytest.mark.asyncio
async def test_seed_default_templates_and_collect_due_reminders(session: AsyncSession) -> None:
    await seed_default_reminder_templates(session)
    await seed_test_customers(session, today=date(2027, 1, 1))

    templates = (
        await session.scalars(select(ReminderTemplate).order_by(ReminderTemplate.days_before.desc()))
    ).all()
    due_items = await collect_due_reminders(session, today=date(2027, 1, 1))

    assert [template.days_before for template in templates] == [7, 3, 1, 0]
    assert [item.customer.name for item in due_items] == ["客户D", "客户C", "客户B", "客户A"]

    await log_reminder_sent(session, due_items[0].customer, due_items[0].days_left, due_items[0].message)
    due_items_after_log = await collect_due_reminders(session, today=date(2027, 1, 1))

    assert [item.customer.name for item in due_items_after_log] == ["客户C", "客户B", "客户A"]
    assert await session.scalar(select(func.count()).select_from(ReminderLog)) == 1


@pytest.mark.asyncio
async def test_delete_customer_cascades_related_records(session: AsyncSession) -> None:
    customer = await ensure_customer_bundle(
        session=session,
        customer_name="客户A",
        server_host="1.1.1.1",
        domain_name="example.com",
        expires_on=date(2027, 1, 1),
    )
    session.add(
        PaymentOrder(
            customer_id=customer.id,
            receive_address="T-address",
        )
    )
    session.add(
        DeploymentTask(
            customer_id=customer.id,
            status="queued",
            deploy_type="bootstrap",
        )
    )
    await session.commit()

    await delete_customer_bundle(session, "客户A")

    assert await session.scalar(select(func.count()).select_from(Customer)) == 0
    assert await session.scalar(select(func.count()).select_from(Server)) == 0
    assert await session.scalar(select(func.count()).select_from(Domain)) == 0
    assert await session.scalar(select(func.count()).select_from(PaymentOrder)) == 0
    assert await session.scalar(select(func.count()).select_from(DeploymentTask)) == 0


@pytest.mark.parametrize(
    ("value", "validator"),
    [
        ("999.1.1.1", validate_server_host),
        ("bad_domain", validate_domain_name),
    ],
)
def test_input_validators_raise(value: str, validator) -> None:
    with pytest.raises(ValueError):
        validator(value)


def test_parse_expires_on_requires_iso_date() -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        parse_expires_on("2027/01/01")
