from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TokenStatus(Enum):
    BONDING_CURVE = "bonding_curve"
    GRADUATING = "graduating"
    PUMP_SWAP = "pump_swap"
    BOOST_ACTIVE = "boost_active"
    BOOST_COMPLETE = "boost_complete"


class BondingCurveStage(Enum):
    EARLY = "early"
    MID = "mid"
    LATE = "late"
    THRESHOLD = "threshold"


@dataclass
class BondingCurveInfo:
    token_mint: str
    sol_deposited: float
    tokens_sold: float
    tokens_remaining: float
    virtual_sol_reserves: float
    virtual_token_reserves: float
    market_cap_usd: float
    stage: BondingCurveStage
    completion_percent: float


@dataclass
class TokenInfo:
    mint: str
    name: str
    symbol: str
    uri: str
    creator: str
    created_at: datetime
    status: TokenStatus = TokenStatus.BONDING_CURVE
    bonding_curve: BondingCurveInfo = None
    pumpswap_pool: str = None
    boost_start_time: datetime = None
    boost_end_time: datetime = None
    boost_sol_spent: float = 0.0
    boost_tokens_burned: float = 0.0


@dataclass
class TradeSignal:
    token: TokenInfo
    action: str
    confidence: float
    reason: str
    suggested_amount_sol: float
    suggested_slippage: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BoostMetrics:
    token_mint: str
    boost_start: datetime
    boost_end: datetime = None
    total_sol_spent: float = 0.0
    total_tokens_burned: float = 0.0
    price_impact_percent: float = 0.0
    volume_during_boost: float = 0.0
    is_complete: bool = False
