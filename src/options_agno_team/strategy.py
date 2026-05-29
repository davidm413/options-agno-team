"""Regime-aware options strategy proposals."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from options_agno_team.adapters.base import MarketDataAdapter
from options_agno_team.config import AppConfig
from options_agno_team.models import (
    DirectionalBias,
    OrderLeg,
    RegimeSnapshot,
    StrategyProposal,
    StrategyType,
    VolatilityRegime,
)
from options_agno_team.option_selection import OptionSelector


LIVE_CAPABLE = {
    StrategyType.BULL_CALL_DEBIT_SPREAD,
    StrategyType.BEAR_PUT_DEBIT_SPREAD,
    StrategyType.BULL_PUT_CREDIT_SPREAD,
    StrategyType.BEAR_CALL_CREDIT_SPREAD,
}


class StrategyEngine:
    def __init__(
        self,
        adapter: MarketDataAdapter,
        config: AppConfig | None = None,
        option_selector: OptionSelector | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or AppConfig()
        self.option_selector = option_selector or OptionSelector(adapter, self.config)

    def propose(self, regime: RegimeSnapshot) -> StrategyProposal:
        strategy = _strategy_for_regime(regime)
        quote = self.adapter.get_quotes([regime.symbol])[regime.symbol]
        spot = quote.last or quote.mid
        if spot is None:
            raise ValueError(f"No usable quote for {regime.symbol}")
        selection = self.option_selector.select(
            strategy,
            regime.symbol,
            spot=spot,
            quantity=self.config.default_quantity,
            as_of=quote.timestamp,
            iv_rank=regime.features.iv_rank,
        )
        max_loss = _max_loss(
            strategy,
            list(selection.legs),
            selection.estimated_credit,
            selection.estimated_debit,
            self.config.default_quantity,
        )
        proposal_id = str(uuid5(NAMESPACE_URL, f"{regime.symbol}:{regime.timestamp}:{strategy.value}"))
        rationale = (
            f"regime={regime.regime_label}",
            f"confidence={regime.confidence:.2f}",
            f"volatility={regime.volatility_regime.value}",
            f"bias={regime.directional_bias.value}",
            *selection.rationale,
        )
        return StrategyProposal(
            proposal_id=proposal_id,
            symbol=regime.symbol,
            strategy_type=strategy,
            regime=regime,
            quantity=self.config.default_quantity,
            legs=selection.legs,
            estimated_credit=selection.estimated_credit,
            estimated_debit=selection.estimated_debit,
            max_loss=max_loss,
            rationale=rationale,
            is_live_capable=strategy in LIVE_CAPABLE,
        )


def _strategy_for_regime(regime: RegimeSnapshot) -> StrategyType:
    vol = regime.volatility_regime
    bias = regime.directional_bias
    if vol is VolatilityRegime.LOW and bias is DirectionalBias.NEUTRAL_CHOPPY:
        return StrategyType.SHORT_IRON_CONDOR
    if vol is VolatilityRegime.LOW and bias is DirectionalBias.BULLISH:
        return StrategyType.BULL_PUT_CREDIT_SPREAD
    if vol is VolatilityRegime.LOW and bias is DirectionalBias.BEARISH:
        return StrategyType.BEAR_CALL_CREDIT_SPREAD
    if vol is VolatilityRegime.HIGH and bias is DirectionalBias.BULLISH:
        return StrategyType.BULL_CALL_DEBIT_SPREAD
    if vol is VolatilityRegime.HIGH and bias is DirectionalBias.BEARISH:
        return StrategyType.BEAR_PUT_DEBIT_SPREAD
    if vol is VolatilityRegime.HIGH and bias is DirectionalBias.NEUTRAL_CHOPPY:
        return StrategyType.SHORT_IRON_CONDOR
    if bias is DirectionalBias.BULLISH:
        return StrategyType.BULL_CALL_DEBIT_SPREAD
    if bias is DirectionalBias.BEARISH:
        return StrategyType.BEAR_PUT_DEBIT_SPREAD
    return StrategyType.CALENDAR_SPREAD


def _max_loss(
    strategy: StrategyType,
    legs: list[OrderLeg],
    credit: float | None,
    debit: float | None,
    quantity: int,
) -> float:
    if strategy in {StrategyType.BULL_CALL_DEBIT_SPREAD, StrategyType.BEAR_PUT_DEBIT_SPREAD, StrategyType.CALENDAR_SPREAD}:
        return round((debit or 0.0) * 100 * quantity, 2)
    if strategy in {StrategyType.BULL_PUT_CREDIT_SPREAD, StrategyType.BEAR_CALL_CREDIT_SPREAD}:
        width = abs(legs[0].strike - legs[1].strike)
        return round(max(width - (credit or 0.0), 0.0) * 100 * quantity, 2)
    put_width = abs(legs[0].strike - legs[1].strike)
    call_width = abs(legs[2].strike - legs[3].strike)
    return round(max(max(put_width, call_width) - (credit or 0.0), 0.0) * 100 * quantity, 2)
