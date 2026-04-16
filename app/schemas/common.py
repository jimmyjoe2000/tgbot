from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"detail": "资源不存在"}})

    detail: str = Field(description="错误详情，适合直接向调用方展示。")
