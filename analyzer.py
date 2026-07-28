from typing import Optional, List
from datetime import datetime

from models import (
    TokenInfo,
    TokenStatus,
    BondingCurveInfo,
    BondingCurveStage,
    TradeSignal,
)
from config import MIN_MARKET_CAP_USD, MAX_MARKET_CAP_USD, GRADUATION_THRESHOLD_SOL


class TokenAnalyzer:
    def __init__(self):
        self.signal_history = []

    def estimate_graduation_probability(self, curve: BondingCurveInfo) -> float:
        base_prob = curve.completion_percent * 0.8
        if curve.stage == BondingCurveStage.THRESHOLD:
            base_prob = min(base_prob + 15, 95)
        elif curve.stage == BondingCurveStage.LATE:
            base_prob = min(base_prob + 5, 80)
        if curve.market_cap_usd > MIN_MARKET_CAP_USD * 0.8:
            base_prob = min(base_prob + 10, 90)
        return min(base_prob, 95.0)

    def generate_trade_signal(self, token: TokenInfo, trade_amount_sol: float = 0.1) -> Optional[TradeSignal]:
        if not token.bonding_curve:
            return None
        curve = token.bonding_curve

        if curve.completion_percent < 10:
            return TradeSignal(
                token=token, action="watch", confidence=0.3,
                reason="Too early in bonding curve",
                suggested_amount_sol=trade_amount_sol, suggested_slippage=15.0,
            )

        if curve.stage == BondingCurveStage.THRESHOLD:
            grad_prob = self.estimate_graduation_probability(curve)
            if grad_prob > 80:
                return TradeSignal(
                    token=token, action="buy", confidence=grad_prob / 100,
                    reason=f"Near graduation ({curve.completion_percent:.1f}%)",
                    suggested_amount_sol=trade_amount_sol, suggested_slippage=25.0,
                )

        if curve.stage == BondingCurveStage.LATE:
            grad_prob = self.estimate_graduation_probability(curve)
            if grad_prob > 60:
                return TradeSignal(
                    token=token, action="watch_strong", confidence=grad_prob / 100,
                    reason=f"Strong potential ({curve.completion_percent:.1f}%)",
                    suggested_amount_sol=trade_amount_sol * 0.5, suggested_slippage=20.0,
                )

        if token.status == TokenStatus.BOOST_ACTIVE:
            return TradeSignal(
                token=token, action="boost_entry", confidence=0.6,
                reason="BOOST active - potential short-term upside",
                suggested_amount_sol=trade_amount_sol * 0.3, suggested_slippage=30.0,
            )

        return None

    def filter_graduation_candidates(self, tokens: List[TokenInfo]) -> List[TokenInfo]:
        candidates = []
        for token in tokens:
            if not token.bonding_curve:
                continue
            curve = token.bonding_curve
            if curve.completion_percent < 70:
                continue
            if curve.market_cap_usd < MIN_MARKET_CAP_USD * 0.5:
                continue
            if curve.market_cap_usd > MAX_MARKET_CAP_USD * 1.5:
                continue
            candidates.append(token)
        candidates.sort(key=lambda t: t.bonding_curve.completion_percent, reverse=True)
        return candidates

    def calculate_optimal_exit(self, entry_price: float, current_price: float, risk_tolerance: str = "medium") -> dict:
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        if risk_tolerance == "low":
            take_profit, stop_loss = 15.0, -8.0
        elif risk_tolerance == "high":
            take_profit, stop_loss = 50.0, -20.0
        else:
            take_profit, stop_loss = 30.0, -12.0

        should_take_profit = profit_percent >= take_profit
        should_stop_loss = profit_percent <= stop_loss

        return {
            "profit_percent": profit_percent,
            "take_profit_target": take_profit,
            "stop_loss_target": stop_loss,
            "should_take_profit": should_take_profit,
            "should_stop_loss": should_stop_loss,
            "recommendation": "SELL" if should_take_profit else "CUT LOSS" if should_stop_loss else "HOLD",
        }


class PortfolioTracker:
    def __init__(self):
        self.positions = {}
        self.total_invested = 0.0
        self.total_return = 0.0

    def add_position(self, token_mint: str, amount_sol: float, price: float, timestamp: datetime):
        self.positions[token_mint] = {
            "amount_sol": amount_sol, "entry_price": price,
            "timestamp": timestamp, "status": "open",
        }
        self.total_invested += amount_sol

    def close_position(self, token_mint: str, exit_price: float) -> Optional[dict]:
        if token_mint not in self.positions:
            return None
        position = self.positions.pop(token_mint)
        pnl = ((exit_price - position["entry_price"]) / position["entry_price"]) * 100
        pnl_sol = position["amount_sol"] * (pnl / 100)
        self.total_return += pnl_sol
        return {
            "token_mint": token_mint, "entry_price": position["entry_price"],
            "exit_price": exit_price, "pnl_percent": pnl, "pnl_sol": pnl_sol,
        }

    def get_portfolio_summary(self) -> dict:
        open_positions = len([p for p in self.positions.values() if p["status"] == "open"])
        return {
            "total_invested_sol": self.total_invested,
            "total_return_sol": self.total_return,
            "net_pnl_sol": self.total_return - self.total_invested,
            "net_pnl_percent": (self.total_return / self.total_invested * 100) if self.total_invested > 0 else 0,
            "open_positions": open_positions,
        }
