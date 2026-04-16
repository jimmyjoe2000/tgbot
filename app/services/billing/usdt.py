from __future__ import annotations

from decimal import Decimal

import httpx

from app.core.config import settings


class USDTPaymentService:
    def __init__(self) -> None:
        self.base_url = settings.payment_provider_base_url.rstrip("/")
        self.api_key = settings.payment_provider_api_key
        self.network = settings.usdt_network
        self.receive_address = settings.usdt_receive_address

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.receive_address)

    async def query_address_transactions(self, address: str | None = None) -> dict:
        if not self.enabled:
            raise RuntimeError("USDT 链上查询服务未配置。")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        target_address = address or self.receive_address
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                self.base_url,
                params={"address": target_address, "network": self.network},
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def payment_matches(self, expected_amount: float, tx_amount: str | float | int) -> bool:
        return Decimal(str(expected_amount)) == Decimal(str(tx_amount))

