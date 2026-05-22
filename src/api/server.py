"""DeFiLens REST API — FastAPI server for portfolio data and analytics."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core.config import AppConfig, SUPPORTED_CHAINS
from ..core.portfolio import PortfolioSummary
from ..core.prices import PriceFeed
from ..chains.scanner import ChainScanner
from ..chains.yield_tracker import YieldTracker
from ..analytics.engine import AnalyticsEngine

logger = logging.getLogger(__name__)

config = AppConfig.load()
price_feed = PriceFeed(coingecko_key=config.coingecko_key)
scanner = ChainScanner(price_feed)
yield_tracker = YieldTracker()
analytics = AnalyticsEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DeFiLens API starting on %s:%d", config.api_host, config.api_port)
    yield
    await price_feed.close()
    await yield_tracker.close()


app = FastAPI(
    title="DeFiLens API",
    description="Cross-chain DeFi portfolio tracker with yield analytics",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    address: str
    chains: list[str] | None = None


class AlertRequest(BaseModel):
    alert_type: str
    target: str
    threshold: float
    webhook_url: str = ""


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "1.2.0", "chains": list(SUPPORTED_CHAINS.keys())}


@app.get("/api/v1/chains")
async def list_chains():
    return {name: {"chain_id": data["chain_id"], "explorer": data["explorer"]} for name, data in SUPPORTED_CHAINS.items()}


@app.post("/api/v1/scan")
async def scan_wallet(req: ScanRequest):
    """Scan a wallet across one or more chains."""
    if not req.address.startswith("0x") or len(req.address) != 42:
        raise HTTPException(400, "Invalid EVM address")

    chains = req.chains or list(SUPPORTED_CHAINS.keys())
    snapshots = await scanner.scan_wallet(req.address, chains)

    summary = PortfolioSummary(wallets=snapshots)
    risk = analytics.compute_risk_metrics(summary)
    pnl = analytics.compute_pnl(summary)

    return {
        "address": req.address,
        "portfolio": summary.to_dict(),
        "risk_metrics": {
            "concentration_hhi": risk.portfolio_concentration_hhi,
            "chain_diversification": risk.chain_diversification_score,
            "risk_score": risk.risk_score,
            "estimated_annual_yield": risk.estimated_annual_yield,
        },
        "pnl": {
            "current_value_usd": round(pnl.current_value_usd, 2),
            "unrealized_pnl_usd": round(pnl.unrealized_pnl_usd, 2),
            "total_pnl_percent": pnl.total_pnl_percent,
        },
        "wallets": [
            {
                "chain": w.chain,
                "native_balance": round(w.native_balance, 6),
                "native_value_usd": round(w.native_value_usd, 2),
                "token_count": len(w.tokens),
                "total_value_usd": round(w.total_value_usd, 2),
                "tokens": [
                    {"symbol": t.symbol, "balance": round(t.balance, 6), "value_usd": round(t.value_usd, 2)}
                    for t in w.tokens
                ],
            }
            for w in snapshots
        ],
    }


@app.get("/api/v1/prices/{symbol}")
async def get_price(symbol: str):
    price = await price_feed.get_price(symbol)
    if price == 0:
        raise HTTPException(404, f"Price not found for {symbol}")
    return {"symbol": symbol.upper(), "price_usd": price}


@app.get("/api/v1/yields")
async def get_yields(
    chain: str = Query("", description="Filter by chain"),
    min_tvl: float = Query(1_000_000, description="Minimum TVL in USD"),
    limit: int = Query(20, le=100),
):
    """Get top yield farming opportunities."""
    pools = await yield_tracker.get_top_yields(chain=chain, min_tvl=min_tvl, limit=limit)
    return {
        "count": len(pools),
        "pools": [
            {
                "protocol": p.protocol,
                "chain": p.chain,
                "pool_name": p.pool_name,
                "pool_address": p.pool_address,
                "apy": p.apy,
                "reward_apy": p.reward_apy,
                "tvl_usd": round(p.tvl_usd, 2),
            }
            for p in pools
        ],
    }


@app.get("/api/v1/yields/{protocol}")
async def get_protocol_yields(protocol: str, chain: str = ""):
    pools = await yield_tracker.get_protocol_yields(protocol, chain=chain)
    return {"protocol": protocol, "count": len(pools), "pools": [
        {"chain": p.chain, "pool_name": p.pool_name, "apy": p.apy, "tvl_usd": round(p.tvl_usd, 2)}
        for p in pools
    ]}
