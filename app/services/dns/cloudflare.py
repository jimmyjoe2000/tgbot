from __future__ import annotations

import httpx

from app.core.config import settings


class CloudflareDNSService:
    def __init__(self) -> None:
        self.base_url = settings.cloudflare_api_base.rstrip("/")
        self.token = settings.cloudflare_api_token

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("Cloudflare API Token 未配置。")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def get_zone_id(self, zone_name: str) -> str:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            response = await client.get(
                "/zones",
                headers=self._headers(),
                params={"name": zone_name},
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("result", [])
            if not results:
                raise ValueError(f"Cloudflare 中未找到 zone: {zone_name}")
            return results[0]["id"]

    async def upsert_a_record(
        self,
        zone_name: str,
        record_name: str,
        ip_address: str,
        ttl: int = 300,
        proxied: bool = False,
    ) -> dict:
        zone_id = await self.get_zone_id(zone_name)
        record_name = record_name.rstrip(".")

        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            existing = await client.get(
                f"/zones/{zone_id}/dns_records",
                headers=self._headers(),
                params={"type": "A", "name": record_name},
            )
            existing.raise_for_status()
            result = existing.json().get("result", [])
            payload = {
                "type": "A",
                "name": record_name,
                "content": ip_address,
                "ttl": ttl,
                "proxied": proxied,
            }
            if result:
                record_id = result[0]["id"]
                response = await client.put(
                    f"/zones/{zone_id}/dns_records/{record_id}",
                    headers=self._headers(),
                    json=payload,
                )
            else:
                response = await client.post(
                    f"/zones/{zone_id}/dns_records",
                    headers=self._headers(),
                    json=payload,
                )

            response.raise_for_status()
            return response.json()

