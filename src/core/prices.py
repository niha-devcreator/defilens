"""Token price feed with multi-source aggregation and caching."""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PRICE_CACHE_TTL = 120  # seconds


class PriceFeed:
    """Aggregates prices from CoinGecko, DeFiLlama, and on-chain oracles."""

    def __init__(self, coingecko_key: str = ""):
        self._cache: dict[str, tuple[float, float]] = {}  # symbol -> (price, timestamp)
        self._coingecko_key = coingecko_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15)
        return self._client

    async def get_price(self, symbol: str) -> float:
        symbol = symbol.upper()
        cached = self._cache.get(symbol)
        if cached and (time.time() - cached[1]) < PRICE_CACHE_TTL:
            return cached[0]

        price = await self._fetch_price(symbol)
        self._cache[symbol] = (price, time.time())
        return price

    async def get_prices(self, symbols: list[str]) -> dict[str, float]:
        tasks = [self.get_price(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        prices = {}
        for sym, result in zip(symbols, results):
            if isinstance(result, (int, float)):
                prices[sym.upper()] = float(result)
            else:
                logger.warning("Failed to fetch price for %s: %s", sym, result)
                prices[sym.upper()] = 0.0
        return prices

    async def _fetch_price(self, symbol: str) -> float:
        # Try DeFiLlama first (free, no key)
        try:
            client = await self._get_client()
            resp = await client.get(
                f"https://coins.llama.fi/prices/current/coingecko:{symbol.lower()}",
            )
            if resp.status_code == 200:
                data = resp.json()
                coins = data.get("coins", {})
                for key, val in coins.items():
                    return float(val.get("price", 0))
        except Exception as e:
            logger.debug("DeFiLlama failed for %s: %s", symbol, e)

        # Fallback: CoinGecko
        try:
            client = await self._get_client()
            headers = {}
            if self._coingecko_key:
                headers["x-cg-demo-api-key"] = self._coingecko_key
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": symbol.lower(), "vs_currencies": "usd"},
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                for _key, val in data.items():
                    return float(val.get("usd", 0))
        except Exception as e:
            logger.debug("CoinGecko failed for %s: %s", symbol, e)

        return 0.0

    async def close(self):
        if self._client:
            await self._client.aclose()
