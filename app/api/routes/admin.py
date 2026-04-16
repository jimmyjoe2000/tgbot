from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.schemas.common import ErrorResponse
from app.schemas.summary import AdminSummaryResponse
from app.services.customers import build_admin_summary

router = APIRouter()


def require_admin_token(
    x_admin_token: Annotated[
        str,
        Header(
            default="",
            description="管理员接口令牌，请通过 `X-Admin-Token` 请求头传入。",
            examples=["change-me-admin-token"],
        ),
    ],
) -> None:
    if x_admin_token != settings.admin_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员令牌无效")


@router.get(
    "/summary",
    response_model=AdminSummaryResponse,
    summary="获取管理总览",
    description=(
        "返回管理员首页所需的关键运营数据，包括客户、域名、服务器、待支付订单、"
        "排队部署任务和即将到期资源。调用方需要在 `X-Admin-Token` 请求头中提供管理员令牌。"
    ),
    responses={
        200: {
            "description": "成功返回管理总览。",
            "content": {
                "application/json": {
                    "example": {
                        "total_customers": 12,
                        "total_domains": 14,
                        "total_servers": 12,
                        "pending_payments": 2,
                        "queued_deployments": 1,
                        "expiring_resources": [
                            {
                                "resource_type": "domain",
                                "customer_name": "客户A",
                                "identifier": "example.com",
                                "expires_on": "2027-01-01",
                                "days_left": 7,
                            }
                        ],
                    }
                }
            },
        },
        401: {
            "model": ErrorResponse,
            "description": "管理员令牌无效或缺失。",
            "content": {"application/json": {"example": {"detail": "管理员令牌无效"}}},
        },
    },
)
async def admin_summary(
    _: None = Depends(require_admin_token),
    session: AsyncSession = Depends(get_db_session),
) -> AdminSummaryResponse:
    return await build_admin_summary(session)
