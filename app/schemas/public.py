from pydantic import BaseModel


class CustomerConfigResponse(BaseModel):
    customer_code: str
    customer_name: str
    brand_name: str
    logo_url: str | None = None
    theme_primary: str
    theme_secondary: str
    support_text: str | None = None

