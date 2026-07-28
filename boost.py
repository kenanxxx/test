from datetime import datetime
from typing import Optional, List, Dict

from models import TokenInfo, TokenStatus, BoostMetrics
from config import BOOST_WINDOW_SECONDS, BOOST_SOL_AMOUNT


class BOOSTTracker:
    def __init__(self):
        self.active_boosts: Dict[str, BoostMetrics] = {}
        self.completed_boosts: Dict[str, BoostMetrics] = {}
        self.boost_callbacks = []

    def start_boost_tracking(self, token: TokenInfo) -> BoostMetrics:
        metrics = BoostMetrics(
            token_mint=token.mint,
            boost_start=datetime.now(),
        )
        self.active_boosts[token.mint] = metrics
        print(f"[BOOST] Started tracking for {token.symbol or token.mint[:8]}")
        return metrics

    def update_boost_metrics(
        self,
        token_mint: str,
        sol_spent: float = 0.0,
        tokens_burned: float = 0.0,
        volume: float = 0.0,
    ) -> Optional[BoostMetrics]:
        if token_mint not in self.active_boosts:
            return None
        metrics = self.active_boosts[token_mint]
        metrics.total_sol_spent += sol_spent
        metrics.total_tokens_burned += tokens_burned
        metrics.volume_during_boost += volume
        elapsed = (datetime.now() - metrics.boost_start).total_seconds()
        if elapsed > 0 and metrics.volume_during_boost > 0:
            metrics.price_impact_percent = (metrics.total_sol_spent / metrics.volume_during_boost) * 100
        return metrics

    def complete_boost(self, token_mint: str) -> Optional[BoostMetrics]:
        if token_mint not in self.active_boosts:
            return None
        metrics = self.active_boosts.pop(token_mint)
        metrics.boost_end = datetime.now()
        metrics.is_complete = True
        self.completed_boosts[token_mint] = metrics
        duration = (metrics.boost_end - metrics.boost_start).total_seconds()
        print(f"[BOOST] Completed for {token_mint[:8]}... Duration: {duration:.1f}s, SOL spent: {metrics.total_sol_spent:.4f}")
        for callback in self.boost_callbacks:
            callback(metrics)
        return metrics

    def is_boost_active(self, token_mint: str) -> bool:
        return token_mint in self.active_boosts

    def get_boost_time_remaining(self, token_mint: str) -> float:
        if token_mint not in self.active_boosts:
            return 0.0
        elapsed = (datetime.now() - self.active_boosts[token_mint].boost_start).total_seconds()
        return max(0.0, BOOST_WINDOW_SECONDS - elapsed)

    def get_boost_progress(self, token_mint: str) -> float:
        if token_mint not in self.active_boosts:
            return 0.0
        elapsed = (datetime.now() - self.active_boosts[token_mint].boost_start).total_seconds()
        return min(elapsed / BOOST_WINDOW_SECONDS * 100, 100.0)

    def add_boost_callback(self, callback):
        self.boost_callbacks.append(callback)

    def get_all_active_boosts(self) -> List[BoostMetrics]:
        return list(self.active_boosts.values())

    def get_boost_history(self, limit: int = 10) -> List[BoostMetrics]:
        history = list(self.completed_boosts.values())
        history.sort(key=lambda x: x.boost_end or datetime.min, reverse=True)
        return history[:limit]


class BOOSTAnalyzer:
    def __init__(self, tracker: BOOSTTracker):
        self.tracker = tracker

    def calculate_boost_efficiency(self, metrics: BoostMetrics) -> dict:
        if metrics.total_sol_spent == 0:
            return {"efficiency_score": 0, "rating": "N/A"}

        efficiency_score = 0
        if metrics.price_impact_percent > 5:
            efficiency_score += 30
        elif metrics.price_impact_percent > 2:
            efficiency_score += 20
        elif metrics.price_impact_percent > 0:
            efficiency_score += 10

        if metrics.volume_during_boost > metrics.total_sol_spent * 2:
            efficiency_score += 30
        elif metrics.volume_during_boost > metrics.total_sol_spent:
            efficiency_score += 20

        if metrics.total_tokens_burned > 0:
            burn_ratio = metrics.total_tokens_burned / 1_000_000_000
            if burn_ratio > 0.05:
                efficiency_score += 40
            elif burn_ratio > 0.02:
                efficiency_score += 30
            elif burn_ratio > 0.01:
                efficiency_score += 20

        rating = "Low"
        if efficiency_score >= 70:
            rating = "High"
        elif efficiency_score >= 40:
            rating = "Medium"

        return {
            "efficiency_score": efficiency_score,
            "rating": rating,
            "burn_ratio_percent": metrics.total_tokens_burned / 1_000_000_000 * 100,
            "volume_to_spend_ratio": (
                metrics.volume_during_boost / metrics.total_sol_spent
                if metrics.total_sol_spent > 0 else 0
            ),
        }

    def predict_post_boost_movement(self, metrics: BoostMetrics) -> dict:
        analysis = self.calculate_boost_efficiency(metrics)
        prediction = {
            "short_term": "neutral",
            "medium_term": "neutral",
            "confidence": 0.5,
            "factors": [],
        }

        if analysis["rating"] == "High":
            prediction["short_term"] = "bullish"
            prediction["confidence"] = 0.7
            prediction["factors"].append("Strong BOOST efficiency")

        if analysis.get("burn_ratio_percent", 0) > 3:
            prediction["short_term"] = "bullish"
            prediction["confidence"] = min(prediction["confidence"] + 0.1, 0.9)
            prediction["factors"].append("Significant token burn")

        if metrics.total_sol_spent < BOOST_SOL_AMOUNT * 0.5:
            prediction["short_term"] = "bearish"
            prediction["confidence"] = 0.6
            prediction["factors"].append("Low BOOST utilization")

        return prediction

    def generate_boost_report(self, token_mint: str) -> dict:
        if token_mint in self.tracker.active_boosts:
            metrics = self.tracker.active_boosts[token_mint]
            status = "active"
        elif token_mint in self.tracker.completed_boosts:
            metrics = self.tracker.completed_boosts[token_mint]
            status = "completed"
        else:
            return {"error": "No BOOST data found"}

        analysis = self.calculate_boost_efficiency(metrics)
        prediction = self.predict_post_boost_movement(metrics)

        return {
            "token_mint": token_mint,
            "status": status,
            "total_sol_spent": metrics.total_sol_spent,
            "total_tokens_burned": metrics.total_tokens_burned,
            "price_impact_percent": metrics.price_impact_percent,
            "analysis": analysis,
            "prediction": prediction,
        }
