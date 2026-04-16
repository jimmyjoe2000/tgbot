from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ExpiringResourceItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resource_type": "domain",
                "customer_name": "客户A",
                "identifier": "example.com",
                "expires_on": "2027-01-01",
                "days_left": 7,
            }
        }
    )

    resource_type: str = Field(description="资源类型，例如 domain 或 server。")
    customer_name: str = Field(description="所属客户名称。")
    identifier: str = Field(description="资源标识，例如域名或服务器 IP。")
    expires_on: date = Field(description="资源到期日期。")
    days_left: int = Field(description="距离到期剩余天数，0 表示当天到期。")


class AdminSummaryResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
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
    )

    total_customers: int = Field(description="客户总数。")
    total_domains: int = Field(description="域名总数。")
    total_servers: int = Field(description="服务器总数。")
    pending_payments: int = Field(description="待确认支付订单数量。")
    queued_deployments: int = Field(description="排队中的部署任务数量。")
    expiring_resources: list[ExpiringResourceItem] = Field(description="即将到期的资源列表。")
