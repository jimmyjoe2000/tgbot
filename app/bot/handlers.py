from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.filters.command import CommandStart
from aiogram.types import Message

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.services.customers import (
    build_admin_summary,
    delete_customer_bundle,
    ensure_customer_bundle,
    get_customer_by_keyword,
    list_customers,
    parse_expires_on,
    update_customer_bundle,
)

router = Router()


def is_admin(message: Message) -> bool:
    if settings.telegram_admin_user_id is None:
        return True
    if message.from_user is None:
        return False
    return message.from_user.id == settings.telegram_admin_user_id


async def reject_if_not_admin(message: Message) -> bool:
    if is_admin(message):
        return False
    await message.answer("当前账号没有管理员权限。")
    return True


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    if await reject_if_not_admin(message):
        return

    await message.answer(
        "指挥中心已启动。\n\n"
        "可用指令：\n"
        "/status 查看总览\n"
        "/add 客户名 服务器IP 域名 到期日期\n"
        "/update 客户名 新IP 新域名 新日期\n"
        "/delete 客户名\n"
        "/list 查看所有客户\n"
        "/my 客户名或客户代号"
    )


@router.message(Command("status"))
async def status_command(message: Message) -> None:
    if await reject_if_not_admin(message):
        return

    async with AsyncSessionFactory() as session:
        summary = await build_admin_summary(session)

    lines = [
        "当前系统概览：",
        f"客户数：{summary.total_customers}",
        f"域名数：{summary.total_domains}",
        f"服务器数：{summary.total_servers}",
        f"待确认收款：{summary.pending_payments}",
        f"待处理部署：{summary.queued_deployments}",
    ]
    if summary.expiring_resources:
        lines.append("")
        lines.append("7 天内到期：")
        for item in summary.expiring_resources[:8]:
            lines.append(
                f"- {item.resource_type} | {item.customer_name} | {item.identifier} | "
                f"{item.expires_on.isoformat()} | 剩余 {item.days_left} 天"
            )

    await message.answer("\n".join(lines))


@router.message(Command("add"))
async def add_command(message: Message, command: CommandObject) -> None:
    if await reject_if_not_admin(message):
        return

    if not command.args:
        await message.answer("用法：/add 客户名 服务器IP 域名 到期日期")
        return

    parts = command.args.split()
    if len(parts) != 4:
        await message.answer("参数数量不对。示例：/add 客户A 1.1.1.1 example.com 2027-01-01")
        return

    customer_name, server_host, domain_name, expires_text = parts
    try:
        expires_on = parse_expires_on(expires_text)
    except ValueError:
        await message.answer("到期日期格式错误，请使用 YYYY-MM-DD。")
        return

    async with AsyncSessionFactory() as session:
        try:
            customer = await ensure_customer_bundle(
                session=session,
                customer_name=customer_name,
                server_host=server_host,
                domain_name=domain_name,
                expires_on=expires_on,
            )
        except ValueError as exc:
            await message.answer(str(exc))
            return

    await message.answer(f"录入成功：{customer.name}（代号：{customer.code}）")


@router.message(Command("update"))
async def update_command(message: Message, command: CommandObject) -> None:
    if await reject_if_not_admin(message):
        return

    if not command.args:
        await message.answer("用法：/update 客户名 新IP 新域名 新日期")
        return

    parts = command.args.split()
    if len(parts) != 4:
        await message.answer("参数数量不对。示例：/update 客户A 2.2.2.2 new.com 2027-01-01")
        return

    customer_keyword, server_host, domain_name, expires_text = parts
    try:
        expires_on = parse_expires_on(expires_text)
    except ValueError:
        await message.answer("到期日期格式错误，请使用 YYYY-MM-DD。")
        return

    async with AsyncSessionFactory() as session:
        try:
            customer = await update_customer_bundle(
                session=session,
                customer_keyword=customer_keyword,
                server_host=server_host,
                domain_name=domain_name,
                expires_on=expires_on,
            )
        except ValueError as exc:
            await message.answer(str(exc))
            return

    await message.answer(f"更新成功：{customer.name}")


@router.message(Command("delete"))
async def delete_command(message: Message, command: CommandObject) -> None:
    if await reject_if_not_admin(message):
        return

    if not command.args:
        await message.answer("用法：/delete 客户名")
        return

    async with AsyncSessionFactory() as session:
        try:
            customer = await delete_customer_bundle(session, command.args)
        except ValueError as exc:
            await message.answer(str(exc))
            return

    await message.answer(f"已删除客户：{customer.name}")


@router.message(Command("list"))
async def list_command(message: Message) -> None:
    if await reject_if_not_admin(message):
        return

    async with AsyncSessionFactory() as session:
        customers = await list_customers(session)

    if not customers:
        await message.answer("当前没有客户数据。")
        return

    lines = ["客户列表："]
    for index, customer in enumerate(customers, start=1):
        server = customer.servers[0] if customer.servers else None
        domain = customer.domains[0] if customer.domains else None
        expires_on = domain.expires_on if domain and domain.expires_on else server.expires_on if server else None
        lines.append(
            f"{index}. {customer.name} | 代号：{customer.code} | "
            f"IP：{server.host if server else '-'} | 域名：{domain.domain if domain else '-'} | "
            f"到期：{expires_on.isoformat() if expires_on else '-'}"
        )

    await message.answer("\n".join(lines))


@router.message(Command("my"))
async def my_command(message: Message, command: CommandObject) -> None:
    if await reject_if_not_admin(message):
        return

    if not command.args:
        await message.answer("用法：/my 客户名或客户代号")
        return

    async with AsyncSessionFactory() as session:
        customer = await get_customer_by_keyword(session, command.args)
        if customer is None:
            await message.answer("未找到对应客户。")
            return

        await message.answer(
            "\n".join(
                [
                    f"客户：{customer.name}",
                    f"代号：{customer.code}",
                    f"状态：{customer.status}",
                    f"品牌名：{customer.brand_name or customer.name}",
                    f"主色：{customer.theme_primary}",
                    f"辅色：{customer.theme_secondary}",
                ]
            )
        )
