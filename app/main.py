from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from app.api.router import api_router
from app.core.config import settings
from app.db.init_db import init_models


class RootResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Telegram Command Center API is running.",
                "docs": "/docs",
            }
        }
    )

    message: str = Field(description="API 启动状态说明。")
    docs: str = Field(description="Swagger UI 文档入口路径。")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_models()
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
    description=(
        "Telegram Command Center API。"
        "提供管理汇总、客户公开配置和系统健康检查接口，"
        "用于 Telegram 运维中枢、自动部署链路和 AI 前端集成。"
    ),
    openapi_tags=[
        {"name": "root", "description": "根路径与文档入口。"},
        {"name": "health", "description": "部署探活与可用性检查。"},
        {"name": "admin", "description": "管理员内部接口，需要管理员令牌。"},
        {"name": "public", "description": "面向客户前端的公开配置接口。"},
    ],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get(
    "/",
    tags=["root"],
    response_model=RootResponse,
    summary="API 根入口",
    description="返回 API 运行状态以及 Swagger 文档入口，便于快速确认服务是否已启动。",
    responses={
        200: {
            "description": "API 已启动。",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Telegram Command Center API is running.",
                        "docs": "/docs",
                    }
                }
            },
        }
    },
)
async def root() -> RootResponse:
    return {
        "message": "Telegram Command Center API is running.",
        "docs": "/docs",
    }


def run() -> None:
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=False)


if __name__ == "__main__":
    run()
