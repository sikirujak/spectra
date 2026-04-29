"""DexScreener API client — fetches DEX token and pool data."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("spectra.dexscreener")


class DexScreenerClient:
    """Client for the DexScreener REST API."""

    def __init__(self, base_url: str = "https://api.dexscreener.com/latest") -> None:
        self.base_url = base_url
        self._http = httpx.AsyncClient(timeout=30)

    async def get_new_pools(self, chain: str = "solana") -> list[dict]:
        """Fetch recently created liquidity pools for a chain."""
        logger.info(f"Fetching new pools for {chain}")
        try:
            resp = await self._http.get(
                f"{self.base_url}/dex/pools/{chain}",
                params={"sort": "timestamp", "order": "desc", "limit": 20},
            )
            if resp.status_code == 200:
                data = resp.json()
                pools = data.get("pairs", data.get("data", []))
                return [p for p in pools if self._is_recent_pool(p)]
            else:
                logger.warning(f"DexScreener API returned {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"DexScreener fetch error: {e}")
            return []

    async def get_trending_tokens(self, chain: str = "solana") -> list[dict]:
        """Fetch trending tokens with significant price/volume changes."""
        logger.info(f"Fetching trending tokens for {chain}")
        try:
            resp = await self._http.get(
                f"{self.base_url}/dex/tokens/trending",
                params={"chain": chain},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("pairs", data.get("data", []))
            else:
                logger.warning(f"DexScreener trending API returned {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"DexScreener trending fetch error: {e}")
            return []

    async def get_token_info(self, token_address: str) -> dict | None:
        """Fetch detailed info for a specific token."""
        try:
            resp = await self._http.get(
                f"{self.base_url}/dex/tokens/{token_address}",
            )
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get("pairs", [])
                return pairs[0] if pairs else None
            return None
        except Exception as e:
            logger.error(f"Token info fetch error for {token_address}: {e}")
            return None

    def _is_recent_pool(self, pool: dict) -> bool:
        """Check if a pool was created within the last 24 hours."""
        try:
            created_at = pool.get("pairCreatedAt", 0)
            if not created_at:
                return True  # No timestamp = assume recent
            from datetime import datetime, timezone
            created = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            return age_hours < 24
        except Exception:
            return True

    async def close(self) -> None:
        await self._http.aclose()