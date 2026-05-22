"""Portfolio data models and state management."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AssetType(str, Enum):
    NATIVE = "native"
    ERC20 = "erc20"
    LP_TOKEN = "lp_token"
    STAKED = "staked"
    YIELD_POSITION = "yield_position"


class Protocol(str, Enum):
    AAVE_V3 = "aave-v3"
    COMPOUND_V3 = "compound-v3"
    UNISWAP_V3 = "uniswap-v3"
    CURVE = "curve"
    LIDO = "lido"
    ROCKET_POOL = "rocket-pool"
    PENDLE = "pendle"
    MORPHO = "morpho"
    YEARN = "yearn-finance"
    CONVEX = "convex"


@dataclass
class TokenBalance:
    symbol: str
    name: str
    contract_address: str
    balance: float
    decimals: int
    price_usd: float = 0.0
    value_usd: float = 0.0
    chain: str = ""
    asset_type: AssetType = AssetType.ERC20

    def __post_init__(self):
        self.value_usd = self.balance * self.price_usd


@dataclass
class YieldPosition:
    protocol: str
    chain: str
    pool_address: str
    pool_name: str
    deposited_usd: float
    current_value_usd: float
    apy: float
    rewards_unclaimed_usd: float = 0.0
    impermanent_loss_usd: float = 0.0
    entry_timestamp: float = 0.0

    @property
    def pnl_usd(self) -> float:
        return self.current_value_usd - self.deposited_usd

    @property
    def pnl_percent(self) -> float:
        if self.deposited_usd == 0:
            return 0.0
        return (self.pnl_usd / self.deposited_usd) * 100


@dataclass
class WalletSnapshot:
    address: str
    chain: str
    native_balance: float = 0.0
    native_value_usd: float = 0.0
    tokens: list[TokenBalance] = field(default_factory=list)
    yield_positions: list[YieldPosition] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def total_value_usd(self) -> float:
        token_total = sum(t.value_usd for t in self.tokens)
        yield_total = sum(y.current_value_usd for y in self.yield_positions)
        return self.native_value_usd + token_total + yield_total


@dataclass
class PortfolioSummary:
    wallets: list[WalletSnapshot] = field(default_factory=list)
    last_updated: float = 0.0

    @property
    def total_value_usd(self) -> float:
        return sum(w.total_value_usd for w in self.wallets)

    @property
    def chain_breakdown(self) -> dict[str, float]:
        breakdown: dict[str, float] = {}
        for w in self.wallets:
            breakdown[w.chain] = breakdown.get(w.chain, 0) + w.total_value_usd
        return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))

    @property
    def top_holdings(self) -> list[TokenBalance]:
        all_tokens = []
        for w in self.wallets:
            all_tokens.extend(w.tokens)
        return sorted(all_tokens, key=lambda t: t.value_usd, reverse=True)[:20]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_value_usd": round(self.total_value_usd, 2),
            "chain_breakdown": {k: round(v, 2) for k, v in self.chain_breakdown.items()},
            "wallet_count": len(self.wallets),
            "last_updated": self.last_updated,
        }
