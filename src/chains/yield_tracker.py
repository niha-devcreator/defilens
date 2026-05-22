"""Yield farming position tracker across DeFi protocols."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.portfolio import YieldPosition
from ..core.config import YIELD_PROTOCOLS

logger = logging.getLogger(__name__)


@dataclass
class YieldPool:
    protocol: str
    chain: str
    pool_name: str
    pool_address: str
    apy: float
    tvl_usd: float
    reward_apy: float = 0.0


class YieldTracker:
    """Tracks yield farming opportunities and user positions via DeFiLlama."""

    DEFILLAMA_YIELDS_URL = "https://yields.llama.fi/pools"
    DEFILLAMA_CHART_URL = "https://yields.llama.fi/chart"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._pools_cache: list[dict[str, Any]] = []
        self._cache_ts: float = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def get_top_yields(self, chain: str = "", min_tvl: float = 1_000_000, limit: int = 20) -> list[YieldPool]:
        pools = await self._fetch_pools()
        filtered = []
        for p in pools:
            if chain and p.get("chain", "").lower() != chain.lower():
                continue
            tvl = p.get("tvlUsd", 0) or 0
            if tvl < min_tvl:
                continue
            apy = p.get("apy", 0) or 0
            if apy <= 0 or apy > 1000:  # filter suspicious APYs
                continue
            filtered.append(YieldPool(
                protocol=p.get("project", "unknown"),
                chain=p.get("chain", ""),
                pool_name=p.get("symbol", ""),
                pool_address=p.get("pool", ""),
                apy=round(apy, 2),
                tvl_usd=tvl,
                reward_apy=round(p.get("apyReward", 0) or 0, 2),
            ))

        filtered.sort(key=lambda x: x.apy, reverse=True)
        return filtered[:limit]

    async def get_protocol_yields(self, protocol: str, chain: str = "") -> list[YieldPool]:
        all_pools = await self.get_top_yields(chain=chain, min_tvl=100_000, limit=500)
        return [p for p in all_pools if p.protocol.lower() == protocol.lower()]

    async def get_historical_apy(self, pool_id: str, days: int = 30) -> list[dict[str, Any]]:
        client = await self._get_client()
        resp = await client.get(f"{self.DEFILLAMA_CHART}/{pool_id}")
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", [])
        return data[-days:] if len(data) > days else data

    async def _fetch_pools(self) -> list[dict[str, Any]]:
        import time
        if self._pools_cache and (time.time() - self._cache_ts) < 300:
            return self._pools_cache

        client = await self._get_client()
        try:
            resp = await client.get(self.DEFILLAMA_YIELDS_URL)
            if resp.status_code == 200:
                self._pools_cache = resp.json().get("data", [])
                self._cache_ts = time.time()
        except Exception as e:
            logger.warning("Failed to fetch yield pools: %s", e)

        return self._pools_cache

    async def close(self):
        if self._client:
            await self._client.aclose()
