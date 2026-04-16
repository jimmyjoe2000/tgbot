from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer
from app.db.session import get_db_session
from app.schemas.public import CustomerConfigResponse

router = APIRouter()


@router.get("/config/{customer_code}", response_model=CustomerConfigResponse)
async def get_customer_config(
    customer_code: str,
    session: AsyncSession = Depends(get_db_session),
) -> CustomerConfigResponse:
    result = await session.scalar(select(Customer).where(Customer.code == customer_code))
    if result is None:
        raise HTTPException(status_code=404, detail="客户配置不存在")

    return CustomerConfigResponse(
        customer_code=result.code,
        customer_name=result.name,
        brand_name=result.brand_name or result.name,
        logo_url=result.logo_url,
        theme_primary=result.theme_primary,
        theme_secondary=result.theme_secondary,
        support_text=result.support_text,
    )

