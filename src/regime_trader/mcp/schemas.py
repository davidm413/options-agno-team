from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import Field

from regime_trader.schemas.base import StrictModel
from regime_trader.schemas.market import AssetClass
from regime_trader.schemas.regime import RegimeOutput
from regime_trader.schemas.trading import (
    ExecutionMode,
    ExecutionRecord,
    RiskDecision,
    StrategyProposal,
)


class ToolError(StrictModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DetectRegimeInput(StrictModel):
    symbol: str
    lookback_bars: int | None = Field(default=None, ge=5)
    include_options: bool = False


class DetectRegimeOutput(StrictModel):
    regime: RegimeOutput | None = None
    error: ToolError | None = None


class CompareRegimesInput(StrictModel):
    symbols: tuple[str, ...] = Field(min_length=1)


class ScanMarketInput(StrictModel):
    symbols: tuple[str, ...] | None = None
    asset_class: AssetClass | None = None


class ProposeOptionsStrategyInput(StrictModel):
    symbol: str
    expiration: date | None = None


class CheckPortfolioRiskInput(StrictModel):
    proposal: StrategyProposal
    account_id: str | None = None


class ExecuteTradeInput(StrictModel):
    proposal: StrategyProposal
    risk_decision: RiskDecision
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    operator_approved: bool = False
    idempotency_key: str


class ExecuteTradeOutput(StrictModel):
    execution: ExecutionRecord | None = None
    error: ToolError | None = None


class RetrainClustersInput(StrictModel):
    dataset_scope: str
    trigger: str


class ReflectOnTradeInput(StrictModel):
    journal_id: str
