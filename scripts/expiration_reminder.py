from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

from aiogram import Bot

from app.core.config import settings
from app.db.init_db import init_models
from app.db.session import AsyncSessionFactory
from app.services.customers import collect_due_reminders, log_reminder_sent


@dataclass(slots=True)
class ReminderResult:
    customer_name: str
    telegram_id: str | None
    days_before: int
    status: str
    message: str


async def dispatch_due_reminders(
    *, dry_run: bool = False, today: date | None = None
) -> list[ReminderResult]:
    async with AsyncSessionFactory() as session:
        due_items = await collect_due_reminders(session, today=today)
        if not due_items:
            return []

        bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token and not dry_run else None
        results: list[ReminderResult] = []
        try:
            for item in due_items:
                status = "dry-run"
                if bot is not None and item.customer.telegram_id:
                    try:
                        await bot.send_message(chat_id=item.customer.telegram_id, text=item.message)
                        status = "sent"
                    except Exception:
                        status = "failed"
                elif not dry_run:
                    status = "skipped"

                await log_reminder_sent(
                    session=session,
                    customer=item.customer,
                    days_before=item.days_left,
                    message=item.message,
                    status=status,
                )
                results.append(
                    ReminderResult(
                        customer_name=item.customer.name,
                        telegram_id=item.customer.telegram_id,
                        days_before=item.days_left,
                        status=status,
                        message=item.message,
                    )
                )
        finally:
            if bot is not None:
                await bot.session.close()

    return results


async def main() -> None:
    await init_models()
    results = await dispatch_due_reminders(dry_run=not bool(settings.telegram_bot_token))
    if not results:
        print("没有需要发送的到期提醒。")
        return

    print("到期提醒扫描结果：")
    for item in results:
        print(
            f"[{item.status}] {item.customer_name} | 提前 {item.days_before} 天 | "
            f"Telegram: {item.telegram_id or '-'}"
        )
        print(item.message)


if __name__ == "__main__":
    asyncio.run(main())
