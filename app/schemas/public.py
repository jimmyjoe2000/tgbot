from pydantic import BaseModel, ConfigDict, Field


class CustomerConfigResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
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
    )

    customer_code: str = Field(description="客户唯一代号，用于前端按租户拉取配置。")
    customer_name: str = Field(description="客户名称。")
    brand_name: str = Field(description="品牌展示名称，可供前端直接显示。")
    logo_url: str | None = Field(default=None, description="客户 Logo 地址，未配置时返回 null。")
    theme_primary: str = Field(description="主色值，HEX 格式。")
    theme_secondary: str = Field(description="辅助色值，HEX 格式。")
    support_text: str | None = Field(default=None, description="前端可直接展示的支持说明。")
