import asyncio
import signal
import sys
from datetime import datetime

from blockchain import SolanaClient
from pumpfun import PumpFunAnalyzer
from boost import BOOSTTracker, BOOSTAnalyzer
from analyzer import TokenAnalyzer, PortfolioTracker
from notifier import TelegramNotifier
from models import TokenStatus
from config import SCAN_INTERVAL_SECONDS, BOOST_WINDOW_SECONDS


class PumpFunBoostBot:
    def __init__(self):
        self.solana_client = SolanaClient()
        self.pumpfun = PumpFunAnalyzer(self.solana_client)
        self.boost_tracker = BOOSTTracker()
        self.boost_analyzer = BOOSTAnalyzer(self.boost_tracker)
        self.token_analyzer = TokenAnalyzer()
        self.portfolio = PortfolioTracker()
        self.notifier = TelegramNotifier()
        self.running = False
        self.scan_count = 0
        self.signal_count = 0

        self.pumpfun.add_graduation_callback(self.on_graduation)
        self.boost_tracker.add_boost_callback(self.on_boost_complete)

    async def on_graduation(self, token):
        print(f"[EVENT] {token.symbol or token.mint[:8]} graduated!")
        await self.notifier.notify_graduation(token)
        self.boost_tracker.start_boost_tracking(token)
        await self.notifier.notify_boost_start(token)

    def on_boost_complete(self, metrics):
        print(f"[EVENT] BOOST completed for {metrics.token_mint[:16]}...")
        asyncio.create_task(self.notifier.notify_boost_complete(metrics))
        analysis = self.boost_analyzer.calculate_boost_efficiency(metrics)
        print(f"[ANALYSIS] Efficiency: {analysis['rating']}")

    async def monitor_boost_progress(self):
        while self.running:
            active_boosts = self.boost_tracker.get_all_active_boosts()
            for metrics in active_boosts:
                token = self.pumpfun.tracked_tokens.get(metrics.token_mint)
                if token:
                    progress = self.boost_tracker.get_boost_progress(metrics.token_mint)
                    remaining = self.boost_tracker.get_boost_time_remaining(metrics.token_mint)
                    if remaining <= 0:
                        self.boost_tracker.complete_boost(metrics.token_mint)
                    elif int(progress) % 25 == 0:
                        await self.notifier.notify_boost_progress(token, progress)
            await asyncio.sleep(1)

    async def scan_and_analyze(self):
        while self.running:
            try:
                self.scan_count += 1
                new_tokens = await self.pumpfun.scan_new_tokens()

                for token in new_tokens:
                    trade_signal = self.token_analyzer.generate_trade_signal(token)
                    if trade_signal and trade_signal.action not in ("watch",):
                        self.signal_count += 1
                        await self.notifier.notify_trade_signal(trade_signal)

                        if trade_signal.action == "buy" and token.bonding_curve:
                            price = token.bonding_curve.virtual_sol_reserves / token.bonding_curve.virtual_token_reserves
                            self.portfolio.add_position(token.mint, trade_signal.suggested_amount_sol, price, datetime.now())

                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            except Exception as e:
                print(f"[ERROR] Scan error: {e}")
                await self.notifier.notify_error(str(e))
                await asyncio.sleep(5)

    async def run(self):
        print("=" * 60)
        print("PUMP.FUN BOOST TRACKER BOT")
        print("=" * 60)
        print(f"Started at: {datetime.now()}")
        print(f"Scan interval: {SCAN_INTERVAL_SECONDS}s")
        print(f"BOOST window: {BOOST_WINDOW_SECONDS}s")
        print("=" * 60)

        self.running = True

        tasks = [
            asyncio.create_task(self.scan_and_analyze()),
            asyncio.create_task(self.monitor_boost_progress()),
        ]

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Received interrupt signal")
        finally:
            self.running = False
            for task in tasks:
                task.cancel()
            print("[SHUTDOWN] Bot stopped")

    def stop(self):
        self.running = False


def main():
    bot = PumpFunBoostBot()

    def signal_handler(sig, frame):
        print("\n[SHUTDOWN] Stopping bot...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
