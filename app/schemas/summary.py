from datetime import date

from pydantic import BaseModel


class ExpiringResourceItem(BaseModel):
    resource_type: str
    customer_name: str
    identifier: str
    expires_on: date
    days_left: int


class AdminSummaryResponse(BaseModel):
    total_customers: int
    total_domains: int
    total_servers: int
    pending_payments: int
    queued_deployments: int
    expiring_resources: list[ExpiringResourceItem]

