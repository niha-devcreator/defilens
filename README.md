<div align="center">

# 🔭 DeFiLens

**Cross-chain DeFi portfolio tracker with yield analytics and real-time monitoring**

[![CI](https://github.com/BankJAY/defilens/actions/workflows/ci.yml/badge.svg)](https://github.com/BankJAY/defilens/actions)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.0-purple.svg)](https://github.com/BankJAY/defilens/releases)

Track DeFi positions across **6 EVM chains**, discover yield opportunities via **10+ protocols**, and get real-time alerts — all from your terminal or API.

</div>

---

## ✨ Features

- **Multi-chain scanning** — Ethereum, BSC, Polygon, Arbitrum, Optimism, Base
- **Portfolio analytics** — PnL tracking, risk metrics, concentration analysis
- **Yield discovery** — Top opportunities from Aave, Compound, Uniswap, Curve, Lido, Pendle, Morpho and more via DeFiLlama
- **Price feed aggregation** — CoinGecko + DeFiLlama with smart caching
- **Alert system** — Price thresholds, portfolio changes, webhook delivery
- **REST API** — FastAPI server for integration with bots, dashboards, and scripts
- **Rich CLI** — Beautiful terminal output with tables, panels, and progress indicators

## 🚀 Quick Start

### Install

```bash
pip install defilens
```

### From source

```bash
git clone https://github.com/BankJAY/defilens.git
cd defilens
pip install -e ".[dev]"
```

### Scan a wallet

```bash
defilens scan 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
```

### Discover yield opportunities

```bash
defilens yields --chain ethereum --limit 10
```

### Get token price

```bash
defilens price ETH
```

### Start API server

```bash
defilens serve
# → http://localhost:8420/docs
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/chains` | List supported chains |
| `POST` | `/api/v1/scan` | Scan wallet portfolio |
| `GET` | `/api/v1/prices/{symbol}` | Get token price |
| `GET` | `/api/v1/yields` | Top yield opportunities |
| `GET` | `/api/v1/yields/{protocol}` | Protocol-specific yields |

### Example: Scan via API

```bash
curl -X POST http://localhost:8420/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "chains": ["ethereum", "arbitrum"]}'
```

## 🏗️ Architecture

```
defilens/
├── src/
│   ├── core/           # Config, portfolio models, price feed
│   │   ├── config.py   # Chain configs, app settings
│   │   ├── portfolio.py # Data models (TokenBalance, WalletSnapshot, YieldPosition)
│   │   └── prices.py   # Multi-source price aggregation
│   ├── chains/         # Blockchain interaction layer
│   │   ├── scanner.py  # Multi-chain wallet scanner
│   │   └── yield_tracker.py # DeFiLlama yield integration
│   ├── analytics/      # Computation engine
│   │   ├── engine.py   # Risk metrics, PnL, allocation analysis
│   │   └── alerts.py   # Alert system with webhook support
│   ├── api/            # REST API
│   │   └── server.py   # FastAPI application
│   └── cli/            # Terminal interface
│       └── main.py     # Click + Rich CLI
├── tests/              # Pytest test suite
├── .github/workflows/  # CI pipeline
├── Dockerfile          # Container deployment
└── docker-compose.yml  # One-command setup
```

## ⚙️ Configuration

Create a `.env` file (see `.env.example`):

```bash
DEFI_LENS_API_KEY=your-api-key
COINGECKO_API_KEY=your-coingecko-key    # optional, has free fallback
MORALIS_API_KEY=your-moralis-key         # optional, for advanced queries
```

## 🐳 Docker

```bash
docker-compose up -d
# API available at http://localhost:8420
```

## 🧪 Testing

```bash
pytest tests/ -v
```

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by [BankJAY](https://github.com/BankJAY)**

</div>
