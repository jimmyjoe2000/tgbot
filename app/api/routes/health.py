from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "ok", "timestamp": "2026-04-17T10:00:00+00:00"}}
    )

    status: str = Field(description="服务健康状态。")
    timestamp: str = Field(description="UTC 时间戳，ISO 8601 格式。")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="用于容器健康检查、网关探活和部署后连通性验证。",
    responses={
        200: {
            "description": "服务可用。",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "timestamp": "2026-04-17T10:00:00+00:00"}
                }
            },
        }
    },
)
async def healthcheck() -> HealthResponse:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
