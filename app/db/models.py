from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    brand_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    theme_primary: Mapped[str] = mapped_column(String(32), default="#dc2626")
    theme_secondary: Mapped[str] = mapped_column(String(32), default="#111827")
    support_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    domains: Mapped[list[Domain]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    servers: Mapped[list[Server]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    payment_orders: Mapped[list[PaymentOrder]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    deployment_tasks: Mapped[list[DeploymentTask]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[NotificationLog]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Domain(TimestampMixin, Base):
    __tablename__ = "domains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    zone_name: Mapped[str] = mapped_column(String(255))
    registrar: Mapped[str] = mapped_column(String(32), default="aliyun")
    dns_provider: Mapped[str] = mapped_column(String(32), default="cloudflare")
    cloudflare_zone_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    auto_dns_enabled: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(32), default="active")

    customer: Mapped[Customer] = relationship(back_populates="domains")


class Server(TimestampMixin, Base):
    __tablename__ = "servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    host: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ssh_port: Mapped[int] = mapped_column(default=22)
    ssh_user: Mapped[str] = mapped_column(String(64), default="root")
    provider: Mapped[str] = mapped_column(String(64), default="aliyun")
    region: Mapped[str] = mapped_column(String(64), default="ap-southeast-1")
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")

    customer: Mapped[Customer] = relationship(back_populates="servers")
    deployment_tasks: Mapped[list[DeploymentTask]] = relationship(
        back_populates="server", cascade="all, delete-orphan"
    )


class PaymentOrder(TimestampMixin, Base):
    __tablename__ = "payment_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    currency: Mapped[str] = mapped_column(String(16), default="USDT")
    network: Mapped[str] = mapped_column(String(32), default="TRON")
    receive_address: Mapped[str] = mapped_column(String(255))
    expected_tx_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="payment_orders")


class DeploymentTask(TimestampMixin, Base):
    __tablename__ = "deployment_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    server_id: Mapped[str | None] = mapped_column(
        ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    requested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    deploy_type: Mapped[str] = mapped_column(String(64), default="bootstrap")
    script_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="deployment_tasks")
    server: Mapped[Server | None] = relationship(back_populates="deployment_tasks")


class NotificationLog(TimestampMixin, Base):
    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    notification_type: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    recipient: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="queued")

    customer: Mapped[Customer | None] = relationship(back_populates="notifications")
