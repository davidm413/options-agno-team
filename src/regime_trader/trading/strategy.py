from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal
from itertools import pairwise
from uuid import uuid4

from regime_trader.config.models import StrategyConfig
from regime_trader.schemas.market import OptionChain, OptionContract, OptionType
from regime_trader.schemas.regime import DirectionalBias, RegimeOutput, RegimeStatus
from regime_trader.schemas.trading import OrderAction, StrategyLeg, StrategyProposal, StrategyType


def _expiration_datetime(contract: OptionContract) -> datetime:
    return datetime.combine(contract.expiration, time(hour=21), tzinfo=UTC)


class StrategyEngine:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def propose(self, regime: RegimeOutput, chain: OptionChain, *, config_version: str) -> StrategyProposal:
        rejection_reasons: list[str] = []
        if regime.status != RegimeStatus.CLASSIFIED:
            rejection_reasons.append("regime_not_classified")
        if regime.confidence < self.config.min_confidence:
            rejection_reasons.append("regime_confidence_below_strategy_threshold")
        if regime.feature_values.get("entropy", 0.0) > self.config.max_entropy_for_directional:
            rejection_reasons.append("entropy_too_high_for_directional_trade")
        if rejection_reasons:
            return self._no_trade(regime, rejection_reasons, config_version=config_version)
        strategy_type = self._map_strategy(regime)
        legs = self._select_legs(strategy_type, chain)
        if not legs:
            return self._no_trade(regime, ("no_contracts_satisfy_filters",), config_version=config_version)
        max_loss, max_gain, estimated_cost = self._estimate_risk(strategy_type, legs)
        alternatives = (
            StrategyType.IRON_CONDOR
            if regime.directional_bias != DirectionalBias.NEUTRAL
            else StrategyType.LONG_STRADDLE,
        )
        return StrategyProposal(
            proposal_id=f"proposal-{uuid4().hex}",
            symbol=regime.symbol,
            strategy_type=strategy_type,
            regime_ref=regime.input_window_ref,
            rationale=(
                f"regime={regime.regime_label}",
                f"confidence={regime.confidence:.2f}",
                f"drivers={','.join(regime.key_drivers)}",
            ),
            legs=tuple(legs),
            alternatives=alternatives,
            pricing_assumptions={"estimated_cost": estimated_cost},
            max_loss=max_loss,
            max_gain=max_gain,
            estimated_cost=estimated_cost,
            exposure_delta=sum(leg.delta or 0 for leg in legs),
            config_version=config_version,
        )

    def _map_strategy(self, regime: RegimeOutput) -> StrategyType:
        if regime.directional_bias == DirectionalBias.BULLISH:
            return self.config.mapping.get("bullish", StrategyType.BULL_CALL_SPREAD)
        if regime.directional_bias == DirectionalBias.BEARISH:
            return self.config.mapping.get("bearish", StrategyType.BEAR_PUT_SPREAD)
        return self.config.mapping.get("neutral", StrategyType.IRON_CONDOR)

    def _select_legs(self, strategy_type: StrategyType, chain: OptionChain) -> list[StrategyLeg]:
        if strategy_type == StrategyType.BULL_CALL_SPREAD:
            return self._vertical(chain, OptionType.CALL, buy_lower=True)
        if strategy_type == StrategyType.BEAR_PUT_SPREAD:
            return self._vertical(chain, OptionType.PUT, buy_lower=False)
        return []

    def _eligible(self, contract: OptionContract) -> bool:
        if contract.mid_price is None:
            return False
        if (contract.open_interest or 0) < self.config.min_open_interest:
            return False
        return not (contract.spread_width is not None and contract.spread_width > self.config.max_bid_ask_spread)

    def _vertical(self, chain: OptionChain, option_type: OptionType, *, buy_lower: bool) -> list[StrategyLeg]:
        contracts = sorted(
            (
                contract
                for contract in chain.contracts
                if contract.option_type == option_type and self._eligible(contract)
            ),
            key=lambda contract: contract.strike,
        )
        for lower, upper in pairwise(contracts):
            if upper.strike - lower.strike < self.config.vertical_width:
                continue
            buy, sell = (lower, upper) if buy_lower else (upper, lower)
            buy_price = buy.mid_price or Decimal("0")
            sell_price = sell.mid_price or Decimal("0")
            if buy_price <= sell_price and buy_lower:
                continue
            return [
                StrategyLeg(
                    option_symbol=buy.option_symbol,
                    underlying_symbol=buy.underlying_symbol,
                    action=OrderAction.BUY_TO_OPEN,
                    option_type=buy.option_type,
                    strike=buy.strike,
                    expiration=_expiration_datetime(buy),
                    quantity=self.config.max_contracts,
                    price=buy_price,
                    delta=buy.greeks.delta if buy.greeks else None,
                ),
                StrategyLeg(
                    option_symbol=sell.option_symbol,
                    underlying_symbol=sell.underlying_symbol,
                    action=OrderAction.SELL_TO_OPEN,
                    option_type=sell.option_type,
                    strike=sell.strike,
                    expiration=_expiration_datetime(sell),
                    quantity=self.config.max_contracts,
                    price=sell_price,
                    delta=sell.greeks.delta if sell.greeks else None,
                ),
            ]
        return []

    def _estimate_risk(
        self, strategy_type: StrategyType, legs: list[StrategyLeg]
    ) -> tuple[Decimal | None, Decimal | None, Decimal]:
        if len(legs) < 2:
            return None, None, Decimal("0")
        buy = next(leg for leg in legs if leg.action == OrderAction.BUY_TO_OPEN)
        sell = next(leg for leg in legs if leg.action == OrderAction.SELL_TO_OPEN)
        width = abs(buy.strike - sell.strike) * Decimal("100") * buy.quantity
        debit = ((buy.price or Decimal("0")) - (sell.price or Decimal("0"))) * Decimal("100") * buy.quantity
        if strategy_type in {StrategyType.BULL_CALL_SPREAD, StrategyType.BEAR_PUT_SPREAD}:
            max_loss = max(Decimal("0"), debit)
            max_gain = max(Decimal("0"), width - max_loss)
            return max_loss, max_gain, debit
        return None, None, debit

    def _no_trade(
        self, regime: RegimeOutput, reasons: tuple[str, ...] | list[str], *, config_version: str
    ) -> StrategyProposal:
        return StrategyProposal(
            proposal_id=f"proposal-{uuid4().hex}",
            symbol=regime.symbol,
            strategy_type=StrategyType.NO_TRADE,
            regime_ref=regime.input_window_ref,
            rationale=("no_trade",),
            legs=(),
            rejection_reasons=tuple(reasons),
            config_version=config_version,
        )
