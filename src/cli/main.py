"""DeFiLens CLI — Rich terminal interface for portfolio tracking."""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.columns import Columns
from rich.text import Text

from ..core.config import AppConfig, SUPPORTED_CHAINS
from ..core.prices import PriceFeed
from ..chains.scanner import ChainScanner
from ..chains.yield_tracker import YieldTracker
from ..analytics.engine import AnalyticsEngine

console = Console()
config = AppConfig.load()


@click.group()
@click.version_option(version="1.2.0", prog_name="defilens")
def cli():
    """DeFiLens — Cross-chain DeFi portfolio tracker with yield analytics."""
    pass


@cli.command()
@click.argument("address")
@click.option("--chains", "-c", multiple=True, help="Chains to scan (default: all)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def scan(address: str, chains: tuple[str, ...], as_json: bool):
    """Scan a wallet across chains and show portfolio breakdown."""
    asyncio.run(_scan(address, list(chains) if chains else None, as_json))


async def _scan(address: str, chains: list[str] | None, as_json: bool):
    price_feed = PriceFeed(coingecko_key=config.coingecko_key)
    scanner = ChainScanner(price_feed)
    engine = AnalyticsEngine()

    with Progress(SpinnerColumn(), TextColumn("[bold blue]Scanning {task.description}...")) as progress:
        task = progress.add_task(address[:10] + "...", total=None)
        snapshots = await scanner.scan_wallet(address, chains)
        progress.update(task, completed=True)

    if not snapshots:
        console.print("[red]No data found for this address.[/red]")
        return

    from ..core.portfolio import PortfolioSummary
    summary = PortfolioSummary(wallets=snapshots)
    risk = engine.compute_risk_metrics(summary)

    # Main panel
    console.print()
    console.print(Panel(
        f"[bold green]${summary.total_value_usd:,.2f}[/bold green]",
        title="💰 Total Portfolio Value",
        subtitle=f"{len(snapwallet := snapshots)} wallet(s) across {len(summary.chain_breakdown)} chain(s)",
    ))

    # Chain breakdown table
    table = Table(title="⛓️ Chain Breakdown", show_header=True, header_style="bold cyan")
    table.add_column("Chain", style="bold")
    table.add_column("Native", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Value (USD)", justify="right")
    table.add_column("% of Total", justify="right")

    for chain, value in summary.chain_breakdown.items():
        pct = (value / summary.total_value_usd * 100) if summary.total_value_usd > 0 else 0
        w = next((w for w in snapshots if w.chain == chain), None)
        native = f"{w.native_balance:.4f}" if w else "0"
        token_count = len(w.tokens) if w else 0
        table.add_row(chain.title(), native, str(token_count), f"${value:,.2f}", f"{pct:.1f}%")

    console.print(table)

    # Top holdings
    holdings = Table(title="📊 Top Holdings", show_header=True, header_style="bold yellow")
    holdings.add_column("Token", style="bold")
    holdings.add_column("Chain")
    holdings.add_column("Balance", justify="right")
    holdings.add_column("Value (USD)", justify="right")

    for t in summary.top_holdings[:10]:
        holdings.add_row(t.symbol, t.chain, f"{t.balance:.4f}", f"${t.value_usd:,.2f}")

    console.print(holdings)

    # Risk panel
    risk_color = {"low": "green", "medium": "yellow", "high": "red"}[risk.risk_score]
    console.print(Panel(
        f"Risk Score: [{risk_color}]{risk.risk_score.upper()}[/{risk_color}]
"
        f"Chain Diversification: {risk.chain_diversification_score}/100
"
        f"Estimated Annual Yield: ${risk.estimated_annual_yield:,.2f}",
        title="⚠️ Risk Metrics",
    ))

    await price_feed.close()


@cli.command()
@click.option("--chain", "-c", default="", help="Filter by chain")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--min-tvl", default=1000000, help="Minimum TVL in USD")
def yields(chain: str, limit: int, min_tvl: int):
    """Show top yield farming opportunities."""
    asyncio.run(_yields(chain, limit, min_tvl))


async def _yields(chain: str, limit: int, min_tvl: int):
    tracker = YieldTracker()

    with Progress(SpinnerColumn(), TextColumn("[bold blue]Fetching yield data...")) as progress:
        task = progress.add_task("DeFiLlama", total=None)
        pools = await tracker.get_top_yields(chain=chain, min_tvl=min_tvl, limit=limit)
        progress.update(task, completed=True)

    table = Table(title="🌾 Top Yield Opportunities", show_header=True, header_style="bold green")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Protocol", style="bold")
    table.add_column("Chain")
    table.add_column("Pool")
    table.add_column("APY", justify="right", style="bold green")
    table.add_column("Reward APY", justify="right")
    table.add_column("TVL", justify="right")

    for i, p in enumerate(pools, 1):
        table.add_row(
            str(i), p.protocol, p.chain, p.pool_name[:25],
            f"{p.apy}%", f"{p.reward_apy}%", f"${p.tvl_usd/1e6:.1f}M",
        )

    console.print(table)
    await tracker.close()


@cli.command()
@click.argument("symbol")
def price(symbol: str):
    """Get current price of a token."""
    asyncio.run(_price(symbol))


async def _price(symbol: str):
    feed = PriceFeed(coingecko_key=config.coingecko_key)
    p = await feed.get_price(symbol)
    if p > 0:
        console.print(f"[bold]{symbol.upper()}[/bold]: [bold green]${p:,.2f}[/bold green]")
    else:
        console.print(f"[red]Price not found for {symbol}[/red]")
    await feed.close()


@cli.command()
def serve():
    """Start the DeFiLens API server."""
    import uvicorn
    console.print(f"[bold green]Starting DeFiLens API on {config.api_host}:{config.api_port}[/bold green]")
    uvicorn.run("src.api.server:app", host=config.api_host, port=config.api_port, reload=False)
