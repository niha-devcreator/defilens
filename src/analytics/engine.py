"""Portfolio analytics engine — PnL, risk metrics, and historical analysis."""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Any

from ..core.portfolio import PortfolioSummary, YieldPosition, TokenBalance

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    portfolio_concentration_hhi: float = 0.0  # Herfindahl-Hirschman Index
    chain_diversification_score: float = 0.0  # 0-100
    protocol_exposure: dict[str, float] = field(default_factory=dict)
    impermanent_loss_total: float = 0.0
    estimated_annual_yield: float = 0.0
    risk_score: str = "medium"  # low, medium, high


@dataclass
class PnLReport:
    total_deposited_usd: float = 0.0
    current_value_usd: float = 0.0
    realized_pnl_usd: float = 0.0
    unrealized_pnl_usd: float = 0.0
    yield_earned_usd: float = 0.0
    impermanent_loss_usd: float = 0.0
    total_pnl_percent: float = 0.0


class AnalyticsEngine:
    """Computes portfolio analytics, risk metrics, and PnL reports."""

    def compute_risk_metrics(self, summary: PortfolioSummary) -> RiskMetrics:
        metrics = RiskMetrics()

        # Chain diversification
        breakdown = summary.chain_breakdown
        total = sum(breakdown.values())
        if total > 0:
            shares = [v / total for v in breakdown.values()]
            hhi = sum(s ** 2 for s in shares)
            metrics.portfolio_concentration_hhi = round(hhi, 4)
            # Normalize: 1 chain = 0 score, equal split across 6 chains = 100
            n_chains = len(breakdown)
            max_hhi = 1.0
            min_hhi = 1.0 / max(n_chains, 1)
            if max_hhi != min_hhi:
                metrics.chain_diversification_score = round((1 - (hhi - min_hhi) / (max_hhi - min_hhi)) * 100, 1)
            else:
                metrics.chain_diversification_score = 100.0 if n_chains > 1 else 0.0

        # Protocol exposure from yield positions
        protocol_values: dict[str, float] = {}
        total_yield = 0.0
        total_il = 0.0
        for wallet in summary.wallets:
            for yp in wallet.yield_positions:
                protocol_values[yp.protocol] = protocol_values.get(yp.protocol, 0) + yp.current_value_usd
                total_yield += yp.current_value_usd * (yp.apy / 100)
                total_il += yp.impermanent_loss_usd

        metrics.protocol_exposure = {k: round(v, 2) for k, v in sorted(protocol_values.items(), key=lambda x: x[1], reverse=True)}
        metrics.estimated_annual_yield = round(total_yield, 2)
        metrics.impermanent_loss_total = round(total_il, 2)

        # Risk score
        if metrics.portfolio_concentration_hhi > 0.6 or total_il > total * 0.1:
            metrics.risk_score = "high"
        elif metrics.portfolio_concentration_hhi > 0.35:
            metrics.risk_score = "medium"
        else:
            metrics.risk_score = "low"

        return metrics

    def compute_pnl(self, summary: PortfolioSummary) -> PnLReport:
        report = PnLReport()
        report.current_value_usd = summary.total_value_usd

        for wallet in summary.wallets:
            for yp in wallet.yield_positions:
                report.total_deposited_usd += yp.deposited_usd
                report.yield_earned_usd += yp.rewards_unclaimed_usd
                report.impermanent_loss_usd += yp.impermanent_loss_usd
                report.unrealized_pnl_usd += yp.pnl_usd

        if report.total_deposited_usd > 0:
            report.total_pnl_percent = round((report.unrealized_pnl_usd / report.total_deposited_usd) * 100, 2)

        return report

    def generate_allocation_chart_data(self, summary: PortfolioSummary) -> dict[str, Any]:
        """Returns data suitable for rendering a pie/bar chart."""
        chain_data = summary.chain_breakdown
        top_tokens = summary.top_holdings[:10]

        return {
            "chains": {k: round(v, 2) for k, v in chain_data.items()},
            "top_tokens": [
                {"symbol": t.symbol, "value_usd": round(t.value_usd, 2), "chain": t.chain}
                for t in top_tokens
            ],
            "total_value_usd": round(summary.total_value_usd, 2),
        }
