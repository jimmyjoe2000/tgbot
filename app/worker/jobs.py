from __future__ import annotations

from aiogram import Bot

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.services.customers import build_admin_summary


async def notify_admin(message: str) -> None:
    if not settings.telegram_bot_token or settings.telegram_admin_user_id is None:
        return
    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(chat_id=settings.telegram_admin_user_id, text=message)
    finally:
        await bot.session.close()


async def daily_expiry_scan() -> None:
    async with AsyncSessionFactory() as session:
        summary = await build_admin_summary(session)

    if not summary.expiring_resources:
        return

    lines = ["到期扫描提醒："]
    for item in summary.expiring_resources[:10]:
        lines.append(
            f"- {item.resource_type} | {item.customer_name} | {item.identifier} | "
            f"{item.expires_on.isoformat()} | 剩余 {item.days_left} 天"
        )
    await notify_admin("\n".join(lines))


async def check_pending_payments() -> None:
    return


async def process_deployment_queue() -> None:
    return

