from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.filters.command import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    ADMIN_MENU_LABELS,
    CUSTOMER_MENU_LABELS,
    build_admin_customer_actions,
    build_admin_delete_confirm,
    build_customer_service_actions,
    build_main_menu,
    build_post_delete_actions,
)
from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.services.customers import (
    build_admin_summary,
    build_my_service_text,
    delete_customer_bundle,
    ensure_customer_bundle,
    get_customer_by_keyword,
    list_customers,
    parse_expires_on,
    update_customer_bundle,
)

router = Router()


def is_admin_user_id(user_id: int | None) -> bool:
    if settings.telegram_admin_user_id is None:
        return True
    return user_id == settings.telegram_admin_user_id


def is_admin(message: Message) -> bool:
    if message.from_user is None:
        return False
    return is_admin_user_id(message.from_user.id)


async def reject_if_not_admin(message: Message) -> bool:
    if is_admin(message):
        return False
    await message.answer("当前账号没有管理员权限。")
    return True


async def reject_callback_if_not_admin(callback: CallbackQuery) -> bool:
    user_id = callback.from_user.id if callback.from_user else None
    if is_admin_user_id(user_id):
        return False
    await callback.answer("当前账号没有管理员权限。", show_alert=True)
    return True


def get_main_menu(message: Message):
    return build_main_menu(is_admin(message))


def get_main_menu_by_user_id(user_id: int | None):
    return build_main_menu(is_admin_user_id(user_id))


def build_add_usage_text() -> str:
    return "用法：/add 客户名 服务器IP 域名 到期日期\n示例：/add 客户A 1.1.1.1 example.com 2027-01-01"


def build_update_usage_text() -> str:
    return "用法：/update 客户名 新IP 新域名 新日期\n示例：/update 客户A 2.2.2.2 new.com 2027-01-01"


def build_help_text(message: Message) -> str:
    customer_lines = [
        "客户可用指令：",
        "/my 查看我的服务信息",
        "/help 查看帮助",
    ]
    if not is_admin(message):
        return "\n".join(customer_lines)

    admin_lines = [
        "",
        "管理员指令：",
        "/status 查看总览",
        "/add 客户名 服务器IP 域名 到期日期",
        "/update 客户名 新IP 新域名 新日期",
        "/delete 客户名",
        "/list 查看所有客户",
        "/my 客户名或客户代号",
    ]
    return "\n".join(customer_lines + admin_lines)


def render_admin_summary_text(summary) -> str:
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
    return "\n".join(lines)


def render_customer_list_text(customers) -> str:
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
    return "\n".join(lines)


async def send_my_service_for_current_user(message: Message) -> None:
    if message.from_user is None:
        await message.answer("无法识别当前 Telegram 账号。", reply_markup=get_main_menu(message))
        return

    async with AsyncSessionFactory() as session:
        service_text = await build_my_service_text(session, str(message.from_user.id))
        if service_text is None:
            await message.answer("当前 Telegram 账号未绑定客户信息，请联系管理员。", reply_markup=get_main_menu(message))
            return

        await message.answer(
            service_text,
            reply_markup=build_customer_service_actions(),
        )


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    await message.answer(
        "指挥中心已启动。\n\n"
        "可直接输入 / 查看命令菜单，或使用下方主菜单按钮进入常用功能。\n\n"
        + build_help_text(message),
        reply_markup=get_main_menu(message),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(build_help_text(message), reply_markup=get_main_menu(message))


@router.message(Command("status"))
async def status_command(message: Message) -> None:
    if await reject_if_not_admin(message):
        return

    async with AsyncSessionFactory() as session:
        summary = await build_admin_summary(session)

    await message.answer(render_admin_summary_text(summary), reply_markup=get_main_menu(message))


@router.message(Command("add"))
async def add_command(message: Message, command: CommandObject) -> None:
    if await reject_if_not_admin(message):
        return

    if not command.args:
        await message.answer(build_add_usage_text(), reply_markup=get_main_menu(message))
        return

    parts = command.args.split()
    if len(parts) != 4:
        await message.answer(
            "参数数量不对。\n" + build_add_usage_text(),
            reply_markup=get_main_menu(message),
        )
        return

    customer_name, server_host, domain_name, expires_text = parts
    try:
        expires_on = parse_expires_on(expires_text)
    except ValueError:
        await message.answer("到期日期格式错误，请使用 YYYY-MM-DD。", reply_markup=get_main_menu(message))
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
            await message.answer(str(exc), reply_markup=get_main_menu(message))
            return

    await message.answer(
        f"录入成功：{customer.name}（代号：{customer.code}）",
        reply_markup=build_admin_customer_actions(customer.code),
    )


@router.message(Command("update"))
async def update_command(message: Message, command: CommandObject) -> None:
    if await reject_if_not_admin(message):
        return

    if not command.args:
        await message.answer(build_update_usage_text(), reply_markup=get_main_menu(message))
        return

    parts = command.args.split()
    if len(parts) != 4:
        await message.answer(
            "参数数量不对。\n" + build_update_usage_text(),
            reply_markup=get_main_menu(message),
        )
        return

    customer_keyword, server_host, domain_name, expires_text = parts
    try:
        expires_on = parse_expires_on(expires_text)
    except ValueError:
        await message.answer("到期日期格式错误，请使用 YYYY-MM-DD。", reply_markup=get_main_menu(message))
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
            await message.answer(str(exc), reply_markup=get_main_menu(message))
            return

    await message.answer(
        f"更新成功：{customer.name}",
        reply_markup=build_admin_customer_actions(customer.code),
    )


@router.message(Command("delete"))
async def delete_command(message: Message, command: CommandObject) -> None:
    if await reject_if_not_admin(message):
        return

    if not command.args:
        await message.answer("用法：/delete 客户名", reply_markup=get_main_menu(message))
        return

    async with AsyncSessionFactory() as session:
        customer = await get_customer_by_keyword(session, command.args, eager=True)
        if customer is None:
            await message.answer("未找到对应客户。", reply_markup=get_main_menu(message))
            return

    await message.answer(
        f"确认删除客户：{customer.name}（代号：{customer.code}）？",
        reply_markup=build_admin_delete_confirm(customer.code),
    )


@router.message(Command("list"))
async def list_command(message: Message) -> None:
    if await reject_if_not_admin(message):
        return

    async with AsyncSessionFactory() as session:
        customers = await list_customers(session)

    if not customers:
        await message.answer("当前没有客户数据。", reply_markup=get_main_menu(message))
        return

    await message.answer(render_customer_list_text(customers), reply_markup=get_main_menu(message))


@router.message(Command("my"))
async def my_command(message: Message, command: CommandObject) -> None:
    if is_admin(message) and command.args:
        async with AsyncSessionFactory() as session:
            customer = await get_customer_by_keyword(session, command.args, eager=True)
            if customer is None:
                await message.answer("未找到对应客户。", reply_markup=get_main_menu(message))
                return

            service_text = await build_my_service_text(session, customer.telegram_id or "")
            if service_text is None:
                await message.answer(
                    "\n".join(
                        [
                            f"客户：{customer.name}",
                            f"状态：{customer.status}",
                            f"到期时间：{customer.expires_on.isoformat() if customer.expires_on else '-'}",
                            f"服务器 IP：{customer.server_ip or '-'}",
                            f"域名：{customer.domain_name or '-'}",
                            f"Telegram 绑定：{customer.telegram_id or '-'}",
                        ]
                    ),
                    reply_markup=build_admin_customer_actions(customer.code),
                )
                return

            await message.answer(service_text, reply_markup=build_admin_customer_actions(customer.code))
        return

    await send_my_service_for_current_user(message)


async def send_customer_overview(
    target: Message | CallbackQuery,
    customer_keyword: str,
    *,
    show_actions: bool = True,
) -> None:
    async with AsyncSessionFactory() as session:
        customer = await get_customer_by_keyword(session, customer_keyword, eager=True)
        if customer is None:
            text = "未找到对应客户。"
        else:
            service_text = await build_my_service_text(session, customer.telegram_id or "")
            if service_text is None:
                expires_on = customer.expires_on.isoformat() if customer.expires_on else "-"
                text = "\n".join(
                    [
                        f"客户：{customer.name}",
                        f"代号：{customer.code}",
                        f"状态：{customer.status}",
                        f"到期时间：{expires_on}",
                        f"服务器 IP：{customer.server_ip or '-'}",
                        f"域名：{customer.domain_name or '-'}",
                        f"Telegram 绑定：{customer.telegram_id or '-'}",
                        f"备注：{customer.note or customer.notes or '-'}",
                    ]
                )
            else:
                text = "\n".join([service_text, f"代号：{customer.code}", f"Telegram 绑定：{customer.telegram_id or '-'}"])

    markup = build_admin_customer_actions(customer_keyword) if show_actions and text != "未找到对应客户。" else None
    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("admin:view:"))
async def admin_view_callback(callback: CallbackQuery) -> None:
    if await reject_callback_if_not_admin(callback):
        return
    if callback.message is None:
        await callback.answer()
        return
    customer_keyword = callback.data.removeprefix("admin:view:")
    await callback.answer("正在加载客户信息")
    await send_customer_overview(callback, customer_keyword)


@router.callback_query(F.data.startswith("admin:edit:"))
async def admin_edit_callback(callback: CallbackQuery) -> None:
    if await reject_callback_if_not_admin(callback):
        return
    customer_keyword = callback.data.removeprefix("admin:edit:")
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.answer(
        f"编辑该客户请直接使用：/update {customer_keyword} 新IP 新域名 新日期",
        reply_markup=get_main_menu_by_user_id(callback.from_user.id if callback.from_user else None),
    )


@router.callback_query(F.data.startswith("admin:delete:"))
async def admin_delete_callback(callback: CallbackQuery) -> None:
    if await reject_callback_if_not_admin(callback):
        return
    customer_keyword = callback.data.removeprefix("admin:delete:")
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.answer(
        f"确认删除客户：{customer_keyword}？",
        reply_markup=build_admin_delete_confirm(customer_keyword),
    )


@router.callback_query(F.data.startswith("admin:delete_confirm:"))
async def admin_delete_confirm_callback(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    if await reject_callback_if_not_admin(callback):
        return

    customer_keyword = callback.data.removeprefix("admin:delete_confirm:")
    async with AsyncSessionFactory() as session:
        try:
            customer = await delete_customer_bundle(session, customer_keyword)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return

    await callback.answer("已删除")
    await callback.message.answer(
        f"已删除客户：{customer.name}",
        reply_markup=build_post_delete_actions(),
    )


@router.callback_query(F.data.startswith("admin:delete_cancel:"))
async def admin_delete_cancel_callback(callback: CallbackQuery) -> None:
    await callback.answer("已取消")
    if callback.message is None:
        return
    await callback.message.answer(
        "删除操作已取消。",
        reply_markup=get_main_menu_by_user_id(callback.from_user.id if callback.from_user else None),
    )


@router.callback_query(F.data == "menu:list")
async def menu_list_callback(callback: CallbackQuery) -> None:
    if await reject_callback_if_not_admin(callback):
        return
    await callback.answer()
    if callback.message is None:
        return
    async with AsyncSessionFactory() as session:
        customers = await list_customers(session)
    text = "当前没有客户数据。" if not customers else render_customer_list_text(customers)
    await callback.message.answer(
        text,
        reply_markup=get_main_menu_by_user_id(callback.from_user.id if callback.from_user else None),
    )


@router.callback_query(F.data == "menu:add_help")
async def menu_add_help_callback(callback: CallbackQuery) -> None:
    if await reject_callback_if_not_admin(callback):
        return
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.answer(
        build_add_usage_text(),
        reply_markup=get_main_menu_by_user_id(callback.from_user.id if callback.from_user else None),
    )


@router.callback_query(F.data == "customer:renew")
async def customer_renew_callback(callback: CallbackQuery) -> None:
    await callback.answer("续费指引已发送")
    if callback.message is None:
        return
    await callback.message.answer(
        "如需续费，请直接联系管理员，并附上客户名、域名和期望续费时长。",
        reply_markup=get_main_menu_by_user_id(callback.from_user.id if callback.from_user else None),
    )


@router.callback_query(F.data == "customer:update_info")
async def customer_update_info_callback(callback: CallbackQuery) -> None:
    await callback.answer("修改指引已发送")
    if callback.message is None:
        return
    await callback.message.answer(
        "如需修改绑定信息，请把新的域名、服务器 IP 或 Telegram 账号发送给管理员处理。",
        reply_markup=get_main_menu_by_user_id(callback.from_user.id if callback.from_user else None),
    )


@router.message(F.text.in_(ADMIN_MENU_LABELS))
async def admin_menu_handler(message: Message) -> None:
    if not is_admin(message):
        return
    if message.text == "系统总览":
        await status_command(message)
        return
    if message.text == "客户列表":
        await list_command(message)
        return
    if message.text == "我的服务":
        await send_my_service_for_current_user(message)
        return
    if message.text == "帮助":
        await help_command(message)
        return
    if message.text == "新增客户格式":
        await message.answer(build_add_usage_text(), reply_markup=get_main_menu(message))
        return
    if message.text == "更新客户格式":
        await message.answer(build_update_usage_text(), reply_markup=get_main_menu(message))


@router.message(F.text.in_(CUSTOMER_MENU_LABELS))
async def customer_menu_handler(message: Message) -> None:
    if is_admin(message):
        return
    if message.text == "我的服务":
        await send_my_service_for_current_user(message)
        return
    if message.text == "帮助":
        await help_command(message)
