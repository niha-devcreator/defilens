"""Tests for portfolio models and analytics engine."""

import pytest
from src.core.portfolio import (
    TokenBalance, WalletSnapshot, PortfolioSummary, AssetType, YieldPosition
)
from src.analytics.engine import AnalyticsEngine


def make_token(symbol="ETH", balance=1.0, price=2000.0, chain="ethereum"):
    return TokenBalance(symbol=symbol, name=symbol, contract_address="0x0", balance=balance, decimals=18, price_usd=price, chain=chain)


def make_yield(protocol="aave-v3", deposited=1000, current=1100, apy=5.0):
    return YieldPosition(
        protocol=protocol, chain="ethereum", pool_address="0x0",
        pool_name="Test Pool", deposited_usd=deposited,
        current_value_usd=current, apy=apy,
    )


class TestTokenBalance:
    def test_value_calculation(self):
        t = make_token(balance=2.5, price=3000)
        assert t.value_usd == 7500.0

    def test_zero_balance(self):
        t = make_token(balance=0, price=100)
        assert t.value_usd == 0.0


class TestWalletSnapshot:
    def test_total_value(self):
        w = WalletSnapshot(address="0x123", chain="ethereum", native_balance=1.0, native_value_usd=2000)
        w.tokens = [make_token(balance=1, price=100)]
        assert w.total_value_usd == 2100.0

    def test_empty_wallet(self):
        w = WalletSnapshot(address="0x123", chain="ethereum")
        assert w.total_value_usd == 0.0


class TestPortfolioSummary:
    def test_chain_breakdown(self):
        w1 = WalletSnapshot(address="0x1", chain="ethereum", native_value_usd=5000)
        w2 = WalletSnapshot(address="0x1", chain="bsc", native_value_usd=3000)
        summary = PortfolioSummary(wallets=[w1, w2])
        assert summary.total_value_usd == 8000
        assert summary.chain_breakdown["ethereum"] == 5000
        assert summary.chain_breakdown["bsc"] == 3000

    def test_top_holdings(self):
        w = WalletSnapshot(address="0x1", chain="ethereum")
        w.tokens = [
            make_token("USDC", 100, 1.0),
            make_token("ETH", 2, 2000),
            make_token("WBTC", 0.5, 40000),
        ]
        summary = PortfolioSummary(wallets=[w])
        top = summary.top_holdings
        assert top[0].symbol == "WBTC"
        assert top[1].symbol == "ETH"


class TestYieldPosition:
    def test_pnl(self):
        yp = make_yield(deposited=1000, current=1200)
        assert yp.pnl_usd == 200
        assert yp.pnl_percent == 20.0

    def test_pnl_negative(self):
        yp = make_yield(deposited=1000, current=800)
        assert yp.pnl_usd == -200
        assert yp.pnl_percent == -20.0


class TestAnalyticsEngine:
    def test_risk_metrics(self):
        w = WalletSnapshot(address="0x1", chain="ethereum", native_value_usd=10000)
        summary = PortfolioSummary(wallets=[w])
        engine = AnalyticsEngine()
        risk = engine.compute_risk_metrics(summary)
        assert risk.risk_score in ("low", "medium", "high")
        assert 0 <= risk.chain_diversification_score <= 100

    def test_pnl_report(self):
        w = WalletSnapshot(address="0x1", chain="ethereum", native_value_usd=5000)
        w.yield_positions = [make_yield(deposited=1000, current=1100, apy=10)]
        summary = PortfolioSummary(wallets=[w])
        engine = AnalyticsEngine()
        pnl = engine.compute_pnl(summary)
        assert pnl.current_value_usd == 6100  # 5000 native + 1100 yield
        assert pnl.unrealized_pnl_usd == 100


class TestAllocationChartData:
    def test_chart_data_structure(self):
        w = WalletSnapshot(address="0x1", chain="ethereum", native_value_usd=5000)
        w.tokens = [make_token("USDC", 1000, 1.0)]
        summary = PortfolioSummary(wallets=[w])
        engine = AnalyticsEngine()
        chart = engine.generate_allocation_chart_data(summary)
        assert "chains" in chart
        assert "top_tokens" in chart
        assert chart["total_value_usd"] == 6000
