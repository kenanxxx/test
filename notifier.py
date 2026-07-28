import httpx
from datetime import datetime
from typing import Optional

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from models import TokenInfo, TradeSignal, BoostMetrics


class TelegramNotifier:
    def __init__(self):
        self.enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def send_message(self, text: str) -> bool:
        if not self.enabled:
            print(f"[NOTIFICATION] {text}")
            return False
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
            response = await self.http_client.post(url, json=payload)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram error: {e}")
            return False

    async def notify_graduation(self, token: TokenInfo):
        symbol = token.symbol or token.mint[:8]
        text = (
            f"Token Graduated!\n\n"
            f"Symbol: {symbol}\n"
            f"Mint: {token.mint}\n\n"
            f"BOOST mode will activate within 5 minutes."
        )
        await self.send_message(text)

    async def notify_boost_start(self, token: TokenInfo):
        symbol = token.symbol or token.mint[:8]
        text = (
            f"BOOST Started!\n\n"
            f"Symbol: {symbol}\n"
            f"Mint: {token.mint}\n\n"
            f"5-minute buyback and burn window active."
        )
        await self.send_message(text)

    async def notify_boost_progress(self, token: TokenInfo, progress: float):
        symbol = token.symbol or token.mint[:8]
        bar = "#" * int(progress / 10) + "-" * (10 - int(progress / 10))
        text = f"BOOST Progress\n\nSymbol: {symbol}\nProgress: [{bar}] {progress:.1f}%"
        await self.send_message(text)

    async def notify_boost_complete(self, metrics: BoostMetrics):
        duration = (metrics.boost_end - metrics.boost_start).total_seconds() if metrics.boost_end else 0
        text = (
            f"BOOST Completed!\n\n"
            f"Token: {metrics.token_mint[:16]}...\n"
            f"Duration: {duration:.1f}s\n"
            f"SOL Spent: {metrics.total_sol_spent:.4f}\n"
            f"Tokens Burned: {metrics.total_tokens_burned:,.0f}\n"
            f"Price Impact: {metrics.price_impact_percent:.2f}%\n"
            f"Volume: {metrics.volume_during_boost:.4f} SOL"
        )
        await self.send_message(text)

    async def notify_trade_signal(self, signal: TradeSignal):
        action_labels = {"buy": "BUY", "sell": "SELL", "watch": "WATCH", "boost_entry": "BOOST"}
        symbol = signal.token.symbol or signal.token.mint[:8]
        text = (
            f"{action_labels.get(signal.action, signal.action)} Signal\n\n"
            f"Symbol: {symbol}\n"
            f"Confidence: {signal.confidence * 100:.1f}%\n"
            f"Reason: {signal.reason}\n"
            f"Amount: {signal.suggested_amount_sol:.4f} SOL\n"
            f"Slippage: {signal.suggested_slippage:.1f}%"
        )
        await self.send_message(text)

    async def notify_error(self, error_msg: str):
        await self.send_message(f"Error: {error_msg}")

    async def notify_daily_summary(self, portfolio: dict, active_boosts: int, signals: int):
        text = (
            f"Daily Summary - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Portfolio:\n"
            f"  Invested: {portfolio['total_invested_sol']:.4f} SOL\n"
            f"  Return: {portfolio['total_return_sol']:.4f} SOL\n"
            f"  Net PnL: {portfolio['net_pnl_sol']:.4f} SOL ({portfolio['net_pnl_percent']:.2f}%)\n\n"
            f"Activity:\n"
            f"  Active BOOSTs: {active_boosts}\n"
            f"  Signals: {signals}"
        )
        await self.send_message(text)
