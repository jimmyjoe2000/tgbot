from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.schemas.summary import AdminSummaryResponse
from app.services.customers import build_admin_summary

router = APIRouter()


def require_admin_token(x_admin_token: str = Header(default="")) -> None:
    if x_admin_token != settings.admin_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员令牌无效")


@router.get("/summary", response_model=AdminSummaryResponse)
async def admin_summary(
    _: None = Depends(require_admin_token),
    session: AsyncSession = Depends(get_db_session),
) -> AdminSummaryResponse:
    return await build_admin_summary(session)
