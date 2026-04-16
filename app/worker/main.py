import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.db.init_db import init_models
from app.worker.jobs import check_pending_payments, daily_expiry_scan, process_deployment_queue


async def run_worker() -> None:
    await init_models()

    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        daily_expiry_scan,
        CronTrigger(hour=settings.scheduler_hour, minute=settings.scheduler_minute),
        id="daily_expiry_scan",
        replace_existing=True,
    )
    scheduler.add_job(
        check_pending_payments,
        "interval",
        minutes=2,
        id="check_pending_payments",
        replace_existing=True,
    )
    scheduler.add_job(
        process_deployment_queue,
        "interval",
        minutes=1,
        id="process_deployment_queue",
        replace_existing=True,
    )
    scheduler.start()

    while True:
        await asyncio.sleep(3600)


def cli() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    cli()

