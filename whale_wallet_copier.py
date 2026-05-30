"""
whale_wallet_copier.py - Whale Wallet Tracker & Copy Trading Alert
By Rizal | github.com/rizalcodes
Monitor whale wallets on Ethereum — get Telegram alerts when whales move
Multi-source: Etherscan V2 + CoinGecko + Web3.py
Output: Real-time alerts + trade signals
"""

import os
import time
import logging
import requests
from web3 import Web3
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "Your_Etherscan_Api_Here")
INFURA_URL        = os.getenv("INFURA_URL",        "https://mainnet.infura.io/v3/Your_Infure_Key_Here")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN",    "Your_Bot_Token_Here")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID",  "Your_Chat_ID_Here")

# Thresholds
MIN_TX_VALUE_USD  = 10000   # minimum $10k buat dianggap whale move
POLL_INTERVAL     = 15      # cek setiap 15 detik
MAX_WALLETS       = 10      # max wallet yang bisa ditrack sekaligus

# Known whale labels
KNOWN_WHALES = {
    "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045": "Vitalik Buterin",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503": "Binance Whale",
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance Hot Wallet",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance Cold Wallet",
    "0x9696f59e4d72e237be84ffd425dcad154bf96976": "Wintermute",
}

# DEX router signatures
DEX_ROUTERS = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3",
    "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f": "SushiSwap",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch V5",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap Universal",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Protocol",
}

# Function selectors
SWAP_SELECTORS = {
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
    "0x38ed1739": "swapExactTokensForTokens",
    "0xfb3bdb41": "swapETHForExactTokens",
    "0x414bf389": "exactInputSingle (V3)",
    "0xb858183f": "exactInput (V3)",
    "0x4a25d94a": "swapTokensForExactETH",
    "0x5c11d795": "swapExactTokensForTokensSupportingFee",
}


# ─────────────────────────────────────────────
# 1. ETHERSCAN CLIENT
# ─────────────────────────────────────────────
class EtherscanClient:
    BASE = "https://api.etherscan.io/v2/api"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def _get(self, params: dict) -> dict:
        params["apikey"]  = self.api_key
        params["chainid"] = 1
        try:
            r = self.session.get(self.BASE, params=params, timeout=15)
            return r.json()
        except Exception as e:
            log.error(f"Etherscan error: {e}")
            return {}

    def get_transactions(self, address: str, start_block: int = 0) -> list:
        """Ambil transactions terbaru dari wallet."""
        data = self._get({
            "module"    : "account",
            "action"    : "txlist",
            "address"   : address,
            "startblock": start_block,
            "sort"      : "desc",
            "page"      : 1,
            "offset"    : 20,
        })
        result = data.get("result", [])
        return result if isinstance(result, list) else []

    def get_token_transfers(self, address: str, start_block: int = 0) -> list:
        """Ambil ERC-20 token transfers."""
        data = self._get({
            "module"    : "account",
            "action"    : "tokentx",
            "address"   : address,
            "startblock": start_block,
            "sort"      : "desc",
            "page"      : 1,
            "offset"    : 20,
        })
        result = data.get("result", [])
        return result if isinstance(result, list) else []

    def get_eth_balance(self, address: str) -> float:
        data = self._get({
            "module" : "account",
            "action" : "balance",
            "address": address,
            "tag"    : "latest",
        })
        try:
            return int(data.get("result", 0)) / 1e18
        except Exception:
            return 0

    def get_latest_block(self) -> int:
        data = self._get({
            "module": "proxy",
            "action": "eth_blockNumber",
        })
        try:
            return int(data.get("result", "0x0"), 16)
        except Exception:
            return 0


# ─────────────────────────────────────────────
# 2. PRICE CLIENT
# ─────────────────────────────────────────────
class PriceClient:
    BASE = "https://api.coingecko.com/api/v3"

    def __init__(self):
        self.session   = requests.Session()
        self._cache    = {}
        self._cache_ts = {}

    def get_eth_price(self) -> float:
        try:
            now = time.time()
            if "eth" in self._cache and now - self._cache_ts.get("eth", 0) < 300:
                return self._cache["eth"]
            r = self.session.get(
                f"{self.BASE}/simple/price",
                params={"ids": "ethereum", "vs_currencies": "usd"},
                timeout=10
            )
            price = r.json().get("ethereum", {}).get("usd", 0)
            self._cache["eth"]    = price
            self._cache_ts["eth"] = now
            return price
        except Exception:
            return 3000  # fallback

    def get_token_price(self, contract_address: str) -> float:
        try:
            addr = contract_address.lower()
            now  = time.time()
            if addr in self._cache and now - self._cache_ts.get(addr, 0) < 300:
                return self._cache[addr]
            r = self.session.get(
                f"{self.BASE}/simple/token_price/ethereum",
                params={"contract_addresses": addr, "vs_currencies": "usd"},
                timeout=10
            )
            price = r.json().get(addr, {}).get("usd", 0)
            self._cache[addr]    = price
            self._cache_ts[addr] = now
            return price
        except Exception:
            return 0

    def get_token_info(self, contract_address: str) -> dict:
        """Ambil nama & symbol token dari CoinGecko."""
        try:
            r = self.session.get(
                f"{self.BASE}/coins/ethereum/contract/{contract_address.lower()}",
                timeout=10
            )
            data = r.json()
            return {
                "name"  : data.get("name", "Unknown"),
                "symbol": data.get("symbol", "???").upper(),
                "price" : data.get("market_data", {}).get("current_price", {}).get("usd", 0),
            }
        except Exception:
            return {"name": "Unknown", "symbol": "???", "price": 0}


# ─────────────────────────────────────────────
# 3. TRANSACTION DECODER
# ─────────────────────────────────────────────
class TxDecoder:
    """Decode transaction input untuk identify swap type."""

    @staticmethod
    def get_tx_type(tx: dict) -> str:
        """Identify jenis transaksi."""
        to_addr    = (tx.get("to") or "").lower()
        input_data = tx.get("input", "0x")
        value      = int(tx.get("value", 0))
        selector   = input_data[:10] if len(input_data) >= 10 else "0x"

        if to_addr in DEX_ROUTERS:
            fn = SWAP_SELECTORS.get(selector, "swap")
            if "ETHForTokens" in fn or "ETHForExact" in fn:
                return "BUY"
            elif "TokensForETH" in fn or "TokensForExact" in fn:
                return "SELL"
            else:
                return "SWAP"
        elif not input_data or input_data == "0x":
            return "TRANSFER"
        elif tx.get("contractAddress"):
            return "DEPLOY"
        else:
            return "CONTRACT_CALL"

    @staticmethod
    def get_dex_name(tx: dict) -> str:
        to_addr = (tx.get("to") or "").lower()
        return DEX_ROUTERS.get(to_addr, "Unknown DEX")

    @staticmethod
    def get_function_name(tx: dict) -> str:
        input_data = tx.get("input", "0x")
        selector   = input_data[:10] if len(input_data) >= 10 else "0x"
        return SWAP_SELECTORS.get(selector, "unknown")


# ─────────────────────────────────────────────
# 4. WHALE TRACKER
# ─────────────────────────────────────────────
class WhaleTracker:
    """Core engine untuk track whale wallets."""

    def __init__(self):
        self.etherscan  = EtherscanClient(ETHERSCAN_API_KEY)
        self.prices     = PriceClient()
        self.decoder    = TxDecoder()
        self.w3         = Web3(Web3.HTTPProvider(INFURA_URL))

        # State per wallet: last seen block
        self.last_block  = {}
        self.wallet_info = {}  # address → {label, eth_balance}

    def add_wallet(self, address: str, label: str = "") -> dict:
        """Tambah wallet ke tracking list."""
        address = address.lower()

        # Get label dari known whales atau custom
        if not label:
            label = KNOWN_WHALES.get(address, f"Whale {address[:6]}...")

        eth_bal = self.etherscan.get_eth_balance(address)
        eth_price = self.prices.get_eth_price()

        self.wallet_info[address] = {
            "address"   : address,
            "label"     : label,
            "eth_balance": eth_bal,
            "usd_value" : round(eth_bal * eth_price, 2),
            "added_at"  : datetime.now().isoformat(),
        }
        self.last_block[address] = self.etherscan.get_latest_block()
        log.info(f"✅ Tracking: {label} ({address[:10]}...)")
        return self.wallet_info[address]

    def remove_wallet(self, address: str):
        address = address.lower()
        self.wallet_info.pop(address, None)
        self.last_block.pop(address, None)

    def get_wallets(self) -> list:
        return list(self.wallet_info.values())

    def check_wallet(self, address: str) -> list:
        """Check satu wallet untuk transaksi baru."""
        address   = address.lower()
        start_blk = self.last_block.get(address, 0)
        new_moves = []

        try:
            txs = self.etherscan.get_transactions(address, start_block=start_blk)
            if not txs:
                return []

            eth_price = self.prices.get_eth_price()
            latest_block = 0

            for tx in txs:
                blk = int(tx.get("blockNumber", 0))
                if blk <= start_blk:
                    continue
                if blk > latest_block:
                    latest_block = blk

                # Filter failed txs
                if tx.get("isError", "0") == "1":
                    continue

                value_eth = int(tx.get("value", 0)) / 1e18
                value_usd = value_eth * eth_price
                tx_type   = self.decoder.get_tx_type(tx)
                dex_name  = self.decoder.get_dex_name(tx)
                fn_name   = self.decoder.get_function_name(tx)

                # Only significant moves
                if value_usd < MIN_TX_VALUE_USD and tx_type not in ("BUY", "SELL", "SWAP"):
                    continue

                move = {
                    "wallet"    : address,
                    "label"     : self.wallet_info.get(address, {}).get("label", "Unknown"),
                    "tx_hash"   : tx.get("hash", ""),
                    "block"     : blk,
                    "timestamp" : datetime.fromtimestamp(int(tx.get("timeStamp", 0))).isoformat(),
                    "type"      : tx_type,
                    "dex"       : dex_name,
                    "function"  : fn_name,
                    "value_eth" : round(value_eth, 4),
                    "value_usd" : round(value_usd, 2),
                    "from"      : tx.get("from", "").lower(),
                    "to"        : (tx.get("to") or "").lower(),
                    "gas_price" : round(int(tx.get("gasPrice", 0)) / 1e9, 2),  # gwei
                }
                new_moves.append(move)

            # Update last seen block
            if latest_block > start_blk:
                self.last_block[address] = latest_block

            # Also check token transfers for swap details
            token_txs = self.etherscan.get_token_transfers(address, start_block=start_blk)
            token_map = defaultdict(list)
            for ttx in token_txs:
                blk = int(ttx.get("blockNumber", 0))
                if blk > start_blk:
                    token_map[ttx.get("hash","")].append(ttx)

            # Enrich moves with token info
            for move in new_moves:
                if move["tx_hash"] in token_map:
                    token_txs_for_hash = token_map[move["tx_hash"]]
                    tokens_in  = [t for t in token_txs_for_hash if t.get("to","").lower() == address]
                    tokens_out = [t for t in token_txs_for_hash if t.get("from","").lower() == address]

                    if tokens_in:
                        t = tokens_in[0]
                        decimals = int(t.get("tokenDecimal", 18))
                        amount   = int(t.get("value", 0)) / (10 ** decimals)
                        move["token_received"] = {
                            "symbol" : t.get("tokenSymbol", "???"),
                            "name"   : t.get("tokenName", "Unknown"),
                            "amount" : round(amount, 4),
                            "contract": t.get("contractAddress", ""),
                        }
                    if tokens_out:
                        t = tokens_out[0]
                        decimals = int(t.get("tokenDecimal", 18))
                        amount   = int(t.get("value", 0)) / (10 ** decimals)
                        move["token_sent"] = {
                            "symbol" : t.get("tokenSymbol", "???"),
                            "name"   : t.get("tokenName", "Unknown"),
                            "amount" : round(amount, 4),
                            "contract": t.get("contractAddress", ""),
                        }

        except Exception as e:
            log.error(f"Check wallet error {address[:10]}: {e}")

        return new_moves

    def scan_all(self) -> list:
        """Scan semua tracked wallets."""
        all_moves = []
        for address in list(self.wallet_info.keys()):
            moves = self.check_wallet(address)
            all_moves.extend(moves)
            if moves:
                log.info(f"🐋 {len(moves)} new move(s) from {address[:10]}...")
            time.sleep(0.5)  # rate limit
        return all_moves


# ─────────────────────────────────────────────
# 5. TELEGRAM BOT
# ─────────────────────────────────────────────
class WhaleBot:
    def __init__(self):
        self.token   = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base    = f"https://api.telegram.org/bot{self.token}"
        self.tracker = WhaleTracker()
        self.offset  = 0
        self.running = True
        self.monitoring = False
        log.info("🤖 WhaleBot initialized")

    def send(self, chat_id: str, text: str):
        try:
            requests.post(
                f"{self.base}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            log.error(f"Send error: {e}")

    def get_updates(self) -> list:
        try:
            r = requests.get(
                f"{self.base}/getUpdates",
                params={"offset": self.offset, "timeout": 10},
                timeout=15
            )
            return r.json().get("result", [])
        except Exception:
            return []

    def _format_move(self, move: dict) -> str:
        """Format whale move untuk Telegram."""
        type_emoji = {
            "BUY"          : "🟢",
            "SELL"         : "🔴",
            "SWAP"         : "🔄",
            "TRANSFER"     : "📤",
            "CONTRACT_CALL": "📋",
            "DEPLOY"       : "🚀",
        }.get(move["type"], "⚪")

        tx_short = move["tx_hash"][:10] + "..." if move["tx_hash"] else "N/A"
        msg = f"""
🐋 *WHALE ALERT*
━━━━━━━━━━━━━━━━━━━━━━
👤 *{move['label']}*
📍 `{move['wallet'][:10]}...{move['wallet'][-4:]}`

{type_emoji} Type     : *{move['type']}*
🏊 DEX      : `{move['dex']}`
💰 Value    : `${move['value_usd']:,.2f}` (`{move['value_eth']} ETH`)
⛽ Gas Price: `{move['gas_price']} Gwei`
🔗 TX       : `{tx_short}`
        """.strip()

        if move.get("token_received"):
            t = move["token_received"]
            msg += f"\n\n📥 *Received:* `{t['amount']:,} {t['symbol']}`"

        if move.get("token_sent"):
            t = move["token_sent"]
            msg += f"\n📤 *Sent:* `{t['amount']:,} {t['symbol']}`"

        msg += f"\n\n⏰ `{move['timestamp'][:19]}`"
        msg += f"\n🔍 [View on Etherscan](https://etherscan.io/tx/{move['tx_hash']})"
        return msg

    # ── Commands ──────────────────────────────
    def cmd_start(self, chat_id: str):
        self.send(chat_id, """
🐋 *Whale Wallet Copier*
━━━━━━━━━━━━━━━━━━━━━━

Track whale wallets & get alerts when they move!

📋 *Commands:*
/add `<address>` — Add wallet to track
/add `<address>` `<label>` — Add with custom label
/remove `<address>` — Remove wallet
/list — Show tracked wallets
/check `<address>` — Manual check wallet
/monitor — Start/stop auto monitoring
/whales — Show known whale addresses
/help — Show commands
        """.strip())

    def cmd_add(self, chat_id: str, args: list):
        if not args:
            self.send(chat_id, "⚠️ Usage: `/add 0x... <optional_label>`")
            return
        address = args[0].strip()
        if not address.startswith("0x") or len(address) != 42:
            self.send(chat_id, "❌ Invalid address format.")
            return
        if len(self.tracker.get_wallets()) >= MAX_WALLETS:
            self.send(chat_id, f"❌ Max {MAX_WALLETS} wallets reached. Remove one first.")
            return

        label = " ".join(args[1:]) if len(args) > 1 else ""
        self.send(chat_id, f"🔍 Adding wallet...\n`{address}`\n⏳ Fetching balance...")
        try:
            info = self.tracker.add_wallet(address, label)
            self.send(chat_id, f"""
✅ *Wallet Added!*
━━━━━━━━━━━━━━━━━━━━━━
👤 Label   : *{info['label']}*
📍 Address : `{address[:10]}...{address[-4:]}`
💰 Balance : `{info['eth_balance']:.4f} ETH` (~`${info['usd_value']:,.2f}`)
📡 Monitoring from block: `{self.tracker.last_block.get(address.lower(), 0):,}`

You'll get alerts on every significant move!
            """.strip())
        except Exception as e:
            self.send(chat_id, f"❌ Error: `{str(e)[:200]}`")

    def cmd_remove(self, chat_id: str, args: list):
        if not args:
            self.send(chat_id, "⚠️ Usage: `/remove 0x...`")
            return
        address = args[0].strip().lower()
        if address in self.tracker.wallet_info:
            label = self.tracker.wallet_info[address]["label"]
            self.tracker.remove_wallet(address)
            self.send(chat_id, f"✅ Removed *{label}* from tracking.")
        else:
            self.send(chat_id, "❌ Wallet not found in tracking list.")

    def cmd_list(self, chat_id: str):
        wallets = self.tracker.get_wallets()
        if not wallets:
            self.send(chat_id, "📭 No wallets tracked.\nUse `/add 0x...` to start tracking.")
            return

        lines = [f"👀 *Tracked Wallets ({len(wallets)}/{MAX_WALLETS})*\n━━━━━━━━━━━━━━━━━━━━━━"]
        for i, w in enumerate(wallets, 1):
            addr = w["address"]
            lines.append(
                f"{i}. *{w['label']}*\n"
                f"   `{addr[:10]}...{addr[-4:]}`\n"
                f"   💰 `{w['eth_balance']:.4f} ETH` (~`${w['usd_value']:,.2f}`)"
            )
        self.send(chat_id, "\n\n".join(lines))

    def cmd_check(self, chat_id: str, args: list):
        if not args:
            self.send(chat_id, "⚠️ Usage: `/check 0x...`")
            return
        address = args[0].strip().lower()

        # Auto-add temporarily if not in list
        temp_added = False
        if address not in self.tracker.wallet_info:
            self.tracker.add_wallet(address)
            temp_added = True

        self.send(chat_id, f"🔍 Checking `{address[:10]}...` for recent moves...\n⏳ Please wait...")
        try:
            # Reset last block to check recent history
            current_block = self.tracker.etherscan.get_latest_block()
            self.tracker.last_block[address] = max(0, current_block - 1000)  # last ~1000 blocks

            moves = self.tracker.check_wallet(address)
            if not moves:
                self.send(chat_id, f"📭 No significant moves found in last ~1000 blocks.")
            else:
                self.send(chat_id, f"📊 Found *{len(moves)}* recent move(s):")
                for move in moves[:5]:  # max 5
                    self.send(chat_id, self._format_move(move))
        except Exception as e:
            self.send(chat_id, f"❌ Error: `{str(e)[:200]}`")

        if temp_added:
            self.tracker.remove_wallet(address)

    def cmd_monitor(self, chat_id: str, args: list):
        if not args:
            status = "ON ✅" if self.monitoring else "OFF ❌"
            self.send(chat_id, f"📡 Auto Monitor: *{status}*\nUse `/monitor on` or `/monitor off`")
            return
        if args[0].lower() == "on":
            if not self.tracker.get_wallets():
                self.send(chat_id, "⚠️ No wallets tracked. Add one first with `/add 0x...`")
                return
            self.monitoring = True
            self.send(chat_id, f"✅ *Auto Monitor ON*\nScanning every {POLL_INTERVAL}s for {len(self.tracker.get_wallets())} wallet(s).")
        elif args[0].lower() == "off":
            self.monitoring = False
            self.send(chat_id, "❌ *Auto Monitor OFF*")

    def cmd_whales(self, chat_id: str):
        lines = ["🐋 *Known Whale Addresses*\n━━━━━━━━━━━━━━━━━━━━━━"]
        for addr, label in KNOWN_WHALES.items():
            lines.append(f"• *{label}*\n  `{addr[:10]}...{addr[-4:]}`")
        lines.append("\nUse `/add <address>` to track any of these!")
        self.send(chat_id, "\n\n".join(lines))

    # ── Message Router ────────────────────────
    def handle(self, message: dict):
        text    = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))
        if not text or not chat_id:
            return

        parts   = text.split()
        command = parts[0].lower()
        args    = parts[1:]
        log.info(f"📨 {command} from {chat_id}")

        if command in ("/start", "/help"): self.cmd_start(chat_id)
        elif command == "/add":            self.cmd_add(chat_id, args)
        elif command == "/remove":         self.cmd_remove(chat_id, args)
        elif command == "/list":           self.cmd_list(chat_id)
        elif command == "/check":          self.cmd_check(chat_id, args)
        elif command == "/monitor":        self.cmd_monitor(chat_id, args)
        elif command == "/whales":         self.cmd_whales(chat_id)
        else:
            self.send(chat_id, "❓ Unknown command. Type /help for commands.")

    # ── Background Monitor ────────────────────
    def _monitor_loop(self):
        """Background loop untuk auto monitoring."""
        log.info("📡 Monitor loop started")
        while self.running:
            if self.monitoring and self.tracker.get_wallets():
                try:
                    moves = self.tracker.scan_all()
                    for move in moves:
                        # Only alert on significant moves
                        if move["value_usd"] >= MIN_TX_VALUE_USD or move["type"] in ("BUY", "SELL", "SWAP"):
                            self.send(self.chat_id, self._format_move(move))
                            time.sleep(1)
                except Exception as e:
                    log.error(f"Monitor loop error: {e}")
            time.sleep(POLL_INTERVAL)

    # ── Main Loop ─────────────────────────────
    def run(self):
        import threading
        log.info("🚀 WhaleBot started!")

        # Start background monitor
        threading.Thread(target=self._monitor_loop, daemon=True).start()

        while self.running:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    if msg:
                        self.handle(msg)
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                log.error(f"Polling error: {e}")
                time.sleep(5)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        # CLI mode: python whale_wallet_copier.py check 0x...
        if len(sys.argv) < 3:
            print("Usage: python whale_wallet_copier.py check <wallet_address>")
            sys.exit(1)

        address = sys.argv[2]
        tracker = WhaleTracker()

        print(f"\n🐋 Checking wallet: {address}")
        info = tracker.add_wallet(address)
        print(f"👤 Label  : {info['label']}")
        print(f"💰 Balance: {info['eth_balance']:.4f} ETH (${info['usd_value']:,.2f})")

        # Check last 500 blocks
        current = tracker.etherscan.get_latest_block()
        tracker.last_block[address.lower()] = max(0, current - 500)

        print(f"\n🔍 Scanning last 500 blocks...")
        moves = tracker.check_wallet(address)

        if not moves:
            print("📭 No significant moves found.")
        else:
            print(f"\n📊 Found {len(moves)} move(s):\n")
            for m in moves:
                print(f"  {m['type']} | ${m['value_usd']:,.2f} | {m['dex']} | {m['timestamp'][:19]}")
                if m.get("token_received"):
                    t = m["token_received"]
                    print(f"    📥 Received: {t['amount']:,} {t['symbol']}")
                if m.get("token_sent"):
                    t = m["token_sent"]
                    print(f"    📤 Sent: {t['amount']:,} {t['symbol']}")
    else:
        bot = WhaleBot()
        bot.run()