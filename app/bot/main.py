import asyncio

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.bot.menus import configure_bot_commands
from app.core.config import settings
from app.db.init_db import init_models


async def run_bot() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 未配置，无法启动 Bot。")
    if not settings.telegram_polling_enabled:
        raise RuntimeError("当前脚手架默认只实现 polling，请将 TELEGRAM_POLLING_ENABLED 设为 true。")

    await init_models()

    bot = Bot(token=settings.telegram_bot_token)
    await configure_bot_commands(bot)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


def cli() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    cli()
