"""DeFiLens configuration management."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

SUPPORTED_CHAINS = {
    "ethereum": {"chain_id": 1, "rpc": "https://eth.llamarpc.com", "explorer": "https://etherscan.io"},
    "bsc": {"chain_id": 56, "rpc": "https://bsc-dataseed.binance.org", "explorer": "https://bscscan.com"},
    "polygon": {"chain_id": 137, "rpc": "https://polygon-rpc.com", "explorer": "https://polygonscan.com"},
    "arbitrum": {"chain_id": 42161, "rpc": "https://arb1.arbitrum.io/rpc", "explorer": "https://arbiscan.io"},
    "optimism": {"chain_id": 10, "rpc": "https://mainnet.optimism.io", "explorer": "https://optimistic.etherscan.io"},
    "base": {"chain_id": 8453, "rpc": "https://mainnet.base.org", "explorer": "https://basescan.org"},
}

YIELD_PROTOCOLS = [
    "aave-v3", "compound-v3", "uniswap-v3", "curve", "convex",
    "yearn-finance", "lido", "rocket-pool", "pendle", "morpho",
]


class ChainConfig(BaseModel):
    name: str
    chain_id: int
    rpc_url: str = ""
    explorer_url: str = ""
    enabled: bool = True


class PortfolioConfig(BaseModel):
    tracked_addresses: list[str] = Field(default_factory=list)
    tracked_chains: list[str] = Field(default_factory=lambda: ["ethereum", "bsc", "polygon"])
    refresh_interval_seconds: int = 60
    alert_threshold_usd: float = 1000.0


class AppConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: os.getenv("DEFI_LENS_API_KEY", ""))
    coingecko_key: str = Field(default_factory=lambda: os.getenv("COINGECKO_API_KEY", ""))
    moralis_key: str = Field(default_factory=lambda: os.getenv("MORALIS_API_KEY", ""))
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    api_host: str = "0.0.0.0"
    api_port: int = 8420
    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".defilens")

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        if path and path.exists():
            import json
            return cls(**json.loads(path.read_text()))
        return cls()


def get_chain_config(chain: str) -> ChainConfig:
    if chain not in SUPPORTED_CHAINS:
        raise ValueError(f"Unsupported chain: {chain}. Available: {list(SUPPORTED_CHAINS.keys())}")
    data = SUPPORTED_CHAINS[chain]
    return ChainConfig(name=chain, chain_id=data["chain_id"], rpc_url=data["rpc"], explorer_url=data["explorer"])
