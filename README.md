# 🐋 Whale Wallet Copier

> Monitor whale wallets on Ethereum & get real-time Telegram alerts when they move — powered by Etherscan V2 + CoinGecko API + Web3.py.

![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square&logo=python)
![Etherscan](https://img.shields.io/badge/Etherscan-V2_API-21325b?style=flat-square)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=flat-square&logo=telegram)
![Ethereum](https://img.shields.io/badge/Ethereum-Mainnet-627EEA?style=flat-square&logo=ethereum)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 🔍 What is Whale Tracking?

Whale tracking is the process of monitoring large Ethereum wallets for significant on-chain activity — helping traders get early signals before the market reacts.

This bot tracks wallets using:
- 📋 **Etherscan V2** — real-time transaction & token transfer data
- 💰 **CoinGecko API** — token prices & USD value calculation
- ⛓️ **Web3.py** — direct Ethereum node interaction via Infura

---

## ✨ Features

- 🐋 **Multi-Wallet Tracking** — monitor up to 10 wallets simultaneously
- 🟢 **BUY / SELL Detection** — identify swap direction automatically
- 💰 **USD Value** — real-time value calculation per transaction
- 🪙 **Token Info** — shows token received/sent per swap
- ⛽ **Gas Tracking** — gas price used by whale per TX
- 🏊 **DEX Detection** — Uniswap V2/V3, SushiSwap, 1inch, 0x
- 🏷️ **Whale Labels** — known whale addresses pre-loaded
- 🤖 **Telegram Bot** — 7 interactive commands
- 📡 **Auto Monitor** — background polling every 15 seconds

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install web3 requests
```

### 2. Set API keys

Open `whale_wallet_copier.py` and configure:

```python
ETHERSCAN_API_KEY = "your_etherscan_key"
INFURA_URL        = "https://mainnet.infura.io/v3/your_infura_key"
TELEGRAM_TOKEN    = "your_telegram_bot_token"
TELEGRAM_CHAT_ID  = "your_chat_id"
```

### 3. Run as Telegram Bot

```bash
python whale_wallet_copier.py
```

### 4. Quick CLI check (one-time)

```bash
python whale_wallet_copier.py check 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
```

---

## 🤖 Telegram Commands

| Command | Description |
|---------|-------------|
| `/add <address>` | Add wallet to track |
| `/add <address> <label>` | Add wallet with custom label |
| `/remove <address>` | Remove wallet from tracking |
| `/list` | Show all tracked wallets |
| `/check <address>` | Manual scan last ~1000 blocks |
| `/monitor on/off` | Toggle auto monitoring |
| `/whales` | Show known whale addresses |

---

## 📊 Sample Output

```
🐋 WHALE ALERT
━━━━━━━━━━━━━━━━━━━━━━
👤 Vitalik Buterin
📍 0xd8dA6BF2...6045

🟢 Type     : BUY
🏊 DEX      : Uniswap V3
💰 Value    : $250,000.00 (83.3 ETH)
⛽ Gas Price: 25.4 Gwei
🔗 TX       : 0x4f2a1b...

📥 Received: 1,250,000 PEPE

⏰ 2026-05-30 22:44:05
🔍 View on Etherscan
```

---

## 🏗️ Architecture

```
whale_wallet_copier.py
├── EtherscanClient     → Etherscan V2 API integration
│   ├── get_transactions()      → fetch wallet TX history
│   ├── get_token_transfers()   → fetch ERC-20 transfers
│   ├── get_eth_balance()       → wallet ETH balance
│   └── get_latest_block()      → current block number
├── PriceClient         → CoinGecko API integration
│   ├── get_eth_price()         → ETH/USD price (5min cache)
│   └── get_token_price()       → token/USD price (5min cache)
├── TxDecoder           → Transaction decoder
│   ├── get_tx_type()           → BUY / SELL / SWAP / TRANSFER
│   ├── get_dex_name()          → identify DEX from router
│   └── get_function_name()     → decode function selector
├── WhaleTracker        → Core tracking engine
│   ├── add_wallet()            → add wallet to watchlist
│   ├── remove_wallet()         → remove wallet
│   ├── check_wallet()          → scan single wallet for new TXs
│   └── scan_all()              → scan all tracked wallets
└── WhaleBot            → Telegram bot with 7 commands
    └── _monitor_loop()         → background polling thread
```

---

## 📡 Data Sources

| Source | Usage |
|--------|-------|
| [Etherscan V2](https://etherscan.io) | Transaction history, token transfers, balances |
| [CoinGecko API](https://coingecko.com) | ETH & token prices in USD |
| [Infura](https://infura.io) | Ethereum RPC node |

---

## 🐋 Pre-loaded Whale Addresses

| Label | Address |
|-------|---------|
| Vitalik Buterin | `0xd8dA6BF2...6045` |
| Binance Whale | `0x47ac0Fb4...503` |
| Binance Hot Wallet | `0x28C6c062...560` |
| Binance Cold Wallet | `0x21a31Ee1...549` |
| Wintermute | `0x9696f59E...976` |

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_TX_VALUE_USD` | $10,000 | Minimum TX value to trigger alert |
| `POLL_INTERVAL` | 15s | How often to scan wallets |
| `MAX_WALLETS` | 10 | Maximum wallets to track simultaneously |

---

## ⚠️ Disclaimer

> **This tool is for informational purposes only. Copying whale trades carries significant risk. Always do your own research.**

---

## 🔧 Requirements

```
web3>=6.0.0
requests>=2.28.0
```

---

## 👤 Author

**Rizal** — [@rizalcodes](https://github.com/rizalcodes)

> Building Web3 tools with Python 🐍⛓️

---

## 📄 License

MIT License — free to use, modify, and distribute.
