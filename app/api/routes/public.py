from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer
from app.db.session import get_db_session
from app.schemas.common import ErrorResponse
from app.schemas.public import CustomerConfigResponse

router = APIRouter()


@router.get(
    "/config/{customer_code}",
    response_model=CustomerConfigResponse,
    summary="获取客户前端配置",
    description=(
        "按客户代号返回品牌、主题色和支持文案等公开配置。"
        "该接口面向客户前端或 AI 生成前端代码调用。"
    ),
    responses={
        200: {
            "description": "成功返回客户配置。",
            "content": {
                "application/json": {
                    "example": {
                        "customer_code": "acme",
                        "customer_name": "Acme Studio",
                        "brand_name": "Acme",
                        "logo_url": "https://cdn.example.com/acme/logo.png",
                        "theme_primary": "#dc2626",
                        "theme_secondary": "#111827",
                        "support_text": "请联系管理员处理续费与配置。",
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "客户配置不存在。",
            "content": {"application/json": {"example": {"detail": "客户配置不存在"}}},
        },
    },
)
async def get_customer_config(
    customer_code: str = Path(
        ...,
        description="客户代号，例如 `acme` 或 `cust-8f3d2a1bcd`。",
        examples=["acme"],
    ),
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
