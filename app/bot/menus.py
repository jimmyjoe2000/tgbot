from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from app.core.config import settings

CUSTOMER_COMMANDS: tuple[BotCommand, ...] = (
    BotCommand(command="start", description="打开指挥中心菜单"),
    BotCommand(command="help", description="查看可用功能说明"),
    BotCommand(command="my", description="查看我的服务信息"),
)

ADMIN_COMMANDS: tuple[BotCommand, ...] = CUSTOMER_COMMANDS + (
    BotCommand(command="status", description="查看系统总览"),
    BotCommand(command="list", description="查看客户列表"),
    BotCommand(command="add", description="新增客户与服务"),
    BotCommand(command="update", description="更新客户信息"),
    BotCommand(command="delete", description="删除客户"),
)


async def configure_bot_commands(bot: Bot) -> None:
    if settings.telegram_admin_user_id is None:
        await bot.set_my_commands(list(ADMIN_COMMANDS), scope=BotCommandScopeDefault())
        return

    await bot.set_my_commands(list(CUSTOMER_COMMANDS), scope=BotCommandScopeDefault())
    await bot.set_my_commands(
        list(ADMIN_COMMANDS),
        scope=BotCommandScopeChat(chat_id=settings.telegram_admin_user_id),
    )
