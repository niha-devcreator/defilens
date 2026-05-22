"""Multi-chain wallet scanner — reads balances and positions across EVM chains."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from web3 import Web3
from web3.exceptions import ContractLogicError

from ..core.config import get_chain_config, SUPPORTED_CHAINS
from ..core.portfolio import TokenBalance, WalletSnapshot, AssetType, YieldPosition
from ..core.prices import PriceFeed

logger = logging.getLogger(__name__)

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
]

# Common token addresses per chain
KNOWN_TOKENS = {
    "ethereum": {
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    },
    "bsc": {
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
    },
    "polygon": {
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    },
}


class ChainScanner:
    """Scans wallet balances and DeFi positions across multiple chains."""

    def __init__(self, price_feed: PriceFeed):
        self.price_feed = price_feed
        self._web3_cache: dict[str, Web3] = {}

    def _get_web3(self, chain: str) -> Web3:
        if chain not in self._web3_cache:
            config = get_chain_config(chain)
            self._web3_cache[chain] = Web3(Web3.HTTPProvider(config.rpc_url))
        return self._web3_cache[chain]

    async def scan_wallet(self, address: str, chains: list[str] | None = None) -> list[WalletSnapshot]:
        if chains is None:
            chains = list(SUPPORTED_CHAINS.keys())

        tasks = [self._scan_chain(address, chain) for chain in chains if chain in SUPPORTED_CHAINS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        snapshots = []
        for result in results:
            if isinstance(result, WalletSnapshot):
                snapshots.append(result)
            elif isinstance(result, Exception):
                logger.warning("Chain scan error: %s", result)

        return snapshots

    async def _scan_chain(self, address: str, chain: str) -> WalletSnapshot:
        w3 = self._get_web3(chain)
        checksum = Web3.to_checksum_address(address)

        # Native balance
        native_wei = w3.eth.get_balance(checksum)
        native_balance = float(Web3.from_wei(native_wei, "ether"))

        native_symbol = {"ethereum": "ETH", "bsc": "BNB", "polygon": "MATIC", "arbitrum": "ETH", "optimism": "ETH", "base": "ETH"}.get(chain, "ETH")
        native_price = await self.price_feed.get_price(native_symbol)

        snapshot = WalletSnapshot(
            address=address,
            chain=chain,
            native_balance=native_balance,
            native_value_usd=native_balance * native_price,
        )

        # ERC-20 tokens
        tokens = KNOWN_TOKENS.get(chain, {})
        for symbol, contract_addr in tokens.items():
            try:
                token_balance = await self._get_erc20_balance(w3, checksum, contract_addr, symbol, chain)
                if token_balance and token_balance.balance > 0:
                    token_balance.price_usd = await self.price_feed.get_price(symbol)
                    token_balance.value_usd = token_balance.balance * token_balance.price_usd
                    snapshot.tokens.append(token_balance)
            except Exception as e:
                logger.debug("Error reading %s on %s: %s", symbol, chain, e)

        return snapshot

    async def _get_erc20_balance(self, w3: Web3, owner: str, contract_addr: str, symbol: str, chain: str) -> TokenBalance | None:
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_addr), abi=ERC20_ABI)
        try:
            balance_raw = contract.functions.balanceOf(owner).call()
            decimals = contract.functions.decimals().call()
            balance = balance_raw / (10 ** decimals)
            if balance <= 0:
                return None
            return TokenBalance(
                symbol=symbol,
                name=symbol,
                contract_address=contract_addr,
                balance=balance,
                decimals=decimals,
                chain=chain,
            )
        except ContractLogicError:
            return None
