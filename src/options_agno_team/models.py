"""Core public models used across adapters, engines, tools, and agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, cast


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class VolatilityRegime(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DirectionalBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL_CHOPPY = "neutral_choppy"


class StrategyType(str, Enum):
    BULL_CALL_DEBIT_SPREAD = "bull_call_debit_spread"
    BEAR_PUT_DEBIT_SPREAD = "bear_put_debit_spread"
    BULL_PUT_CREDIT_SPREAD = "bull_put_credit_spread"
    BEAR_CALL_CREDIT_SPREAD = "bear_call_credit_spread"
    SHORT_IRON_CONDOR = "short_iron_condor"
    CALENDAR_SPREAD = "calendar_spread"


class RiskStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ExecutionStatus(str, Enum):
    DRY_RUN = "dry_run"
    PREFLIGHTED = "preflighted"
    PLACED = "placed"
    REJECTED = "rejected"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class NormalizedBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    session: str = "regular"
    source: str = "fixture"


@dataclass(frozen=True)
class NormalizedQuote:
    symbol: str
    timestamp: datetime
    bid: float | None
    ask: float | None
    last: float | None
    volume: float | None = None
    source: str = "fixture"

    @property
    def mid(self) -> float | None:
        if self.bid is None or self.ask is None:
            return self.last
        return (self.bid + self.ask) / 2


@dataclass(frozen=True)
class OptionContractQuote:
    symbol: str
    underlying: str
    expiration_date: str
    option_type: OptionType
    strike: float
    bid: float | None
    ask: float | None
    last: float | None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None
    implied_volatility: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    source: str = "fixture"

    @property
    def mid(self) -> float | None:
        if self.bid is None or self.ask is None:
            return self.last
        return (self.bid + self.ask) / 2


@dataclass(frozen=True)
class FeatureSnapshot:
    symbol: str
    timestamp: datetime
    returns: tuple[float, ...]
    realized_volatility: float
    wasserstein_distance: float
    entropy: float
    momentum: float
    iv_rank: float | None
    skew: float | None
    term_structure_slope: float | None
    feature_vector: tuple[float, ...]


@dataclass(frozen=True)
class RegimeSnapshot:
    symbol: str
    timestamp: datetime
    volatility_regime: VolatilityRegime
    directional_bias: DirectionalBias
    regime_label: str
    cluster_id: int
    confidence: float
    wasserstein_distance: float
    entropy: float
    key_drivers: tuple[str, ...]
    transition_probability: dict[str, float]
    features: FeatureSnapshot


@dataclass(frozen=True)
class OrderLeg:
    contract_symbol: str
    side: OrderSide
    option_type: OptionType
    strike: float
    expiration_date: str
    quantity: int = 1


@dataclass(frozen=True)
class StrategyProposal:
    proposal_id: str
    symbol: str
    strategy_type: StrategyType
    regime: RegimeSnapshot
    quantity: int
    legs: tuple[OrderLeg, ...]
    estimated_credit: float | None
    estimated_debit: float | None
    max_loss: float
    rationale: tuple[str, ...]
    is_live_capable: bool


@dataclass(frozen=True)
class RiskDecision:
    proposal_id: str
    status: RiskStatus
    approved: bool
    reasons: tuple[str, ...]
    max_loss: float
    risk_budget: float
    portfolio_delta_after: float


@dataclass(frozen=True)
class OrderIntent:
    proposal_id: str
    strategy_type: StrategyType
    symbol: str
    quantity: int
    legs: tuple[OrderLeg, ...]
    limit_price: float


@dataclass(frozen=True)
class ExecutionResult:
    proposal_id: str
    status: ExecutionStatus
    message: str
    order_intent: OrderIntent | None = None
    preflight: dict[str, Any] | None = None
    order_id: str | None = None
    audit: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LiveReadinessReport:
    ready: bool
    execution_mode: str
    checks: dict[str, bool]
    blockers: tuple[str, ...]
    confirmations: tuple[str, ...]
    risk_limits: dict[str, float | int | bool]
    alerting: dict[str, Any]


@dataclass(frozen=True)
class AlertEvent:
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    category: str
    message: str
    proposal_id: str | None = None
    symbol: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperPosition:
    position_id: str
    proposal_id: str
    symbol: str
    strategy_type: StrategyType
    quantity: int
    opened_at: datetime
    updated_at: datetime
    entry_net_price: float
    mark_net_price: float
    unrealized_pnl: float
    status: str = "open"


@dataclass(frozen=True)
class BacktestTrade:
    proposal_id: str
    symbol: str
    strategy_type: StrategyType
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    underlying_return: float
    strategy_return: float
    pnl: float
    max_loss: float
    approved: bool
    regime_label: str
    volatility_regime: VolatilityRegime
    directional_bias: DirectionalBias
    thesis_matched: bool
    outcome: str
    original_thesis: tuple[str, ...]
    outcome_vs_thesis: str


@dataclass(frozen=True)
class BacktestReport:
    report_id: str
    symbols: tuple[str, ...]
    started_at: datetime
    ended_at: datetime
    lookback: int
    min_lookback: int
    holding_period: int
    step: int
    trades: tuple[BacktestTrade, ...]
    win_rate: float
    max_drawdown: float
    average_return: float
    regime_accuracy: float
    strategy_performance: dict[str, dict[str, float]]
    symbol_performance: dict[str, dict[str, float]]
    regime_thesis_performance: dict[str, dict[str, float]]
    regime_thesis_insights: tuple[str, ...]


@dataclass(frozen=True)
class MonitoringEvent:
    event_id: str
    position_id: str
    proposal_id: str
    symbol: str
    timestamp: datetime
    action: str
    triggers: tuple[str, ...]
    original_regime_label: str
    current_regime_label: str
    unrealized_pnl: float
    pnl_pct_of_risk: float
    net_delta: float
    entropy: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class TradeReflection:
    reflection_id: str
    position_id: str
    proposal_id: str
    symbol: str
    strategy_type: StrategyType
    timestamp: datetime
    original_regime_label: str
    current_regime_label: str
    original_thesis: tuple[str, ...]
    thesis_matched: bool
    outcome: str
    pnl: float
    observations: tuple[str, ...]
    original_volatility_regime: VolatilityRegime
    original_directional_bias: DirectionalBias
    current_volatility_regime: VolatilityRegime
    current_directional_bias: DirectionalBias
    outcome_vs_thesis: str


@dataclass(frozen=True)
class LearningReport:
    report_id: str
    generated_at: datetime
    reflections: tuple[TradeReflection, ...]
    performance_by_thesis: dict[str, dict[str, float]]
    performance_by_regime_thesis: dict[str, dict[str, float]]
    insights: tuple[str, ...]


@dataclass(frozen=True)
class RankedTradeCandidate:
    rank: int
    symbol: str
    score: float
    proposal_id: str
    strategy_type: StrategyType
    volatility_regime: VolatilityRegime
    directional_bias: DirectionalBias
    regime_label: str
    confidence: float
    risk_status: RiskStatus
    risk_reasons: tuple[str, ...]
    max_loss: float
    risk_budget: float
    is_live_capable: bool
    rationale: tuple[str, ...]


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: to_jsonable(v) for k, v in asdict(cast(Any, value)).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return value
