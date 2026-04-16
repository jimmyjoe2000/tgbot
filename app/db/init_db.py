from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import engine
from app.services.customers import seed_default_reminder_templates, seed_test_customers


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        await seed_default_reminder_templates(session)
        await seed_test_customers(session)
