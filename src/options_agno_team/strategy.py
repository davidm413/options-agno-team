"""Regime-aware options strategy proposals."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from options_agno_team.adapters.base import MarketDataAdapter
from options_agno_team.config import AppConfig
from options_agno_team.models import (
    DirectionalBias,
    OptionContractQuote,
    OptionType,
    OrderLeg,
    OrderSide,
    RegimeSnapshot,
    StrategyProposal,
    StrategyType,
    VolatilityRegime,
)


LIVE_CAPABLE = {
    StrategyType.BULL_CALL_DEBIT_SPREAD,
    StrategyType.BEAR_PUT_DEBIT_SPREAD,
    StrategyType.BULL_PUT_CREDIT_SPREAD,
    StrategyType.BEAR_CALL_CREDIT_SPREAD,
}


class StrategyEngine:
    def __init__(self, adapter: MarketDataAdapter, config: AppConfig | None = None) -> None:
        self.adapter = adapter
        self.config = config or AppConfig()

    def propose(self, regime: RegimeSnapshot) -> StrategyProposal:
        strategy = _strategy_for_regime(regime)
        quote = self.adapter.get_quotes([regime.symbol])[regime.symbol]
        spot = quote.last or quote.mid
        if spot is None:
            raise ValueError(f"No usable quote for {regime.symbol}")
        expiration = self.adapter.get_option_expirations(regime.symbol)[0]
        chain = self.adapter.get_option_chain(regime.symbol, expiration_date=expiration)
        legs, credit, debit = _build_legs(strategy, chain, spot, self.config.default_quantity)
        max_loss = _max_loss(strategy, legs, credit, debit, self.config.default_quantity)
        proposal_id = str(uuid5(NAMESPACE_URL, f"{regime.symbol}:{regime.timestamp}:{strategy.value}"))
        rationale = (
            f"regime={regime.regime_label}",
            f"confidence={regime.confidence:.2f}",
            f"volatility={regime.volatility_regime.value}",
            f"bias={regime.directional_bias.value}",
        )
        return StrategyProposal(
            proposal_id=proposal_id,
            symbol=regime.symbol,
            strategy_type=strategy,
            regime=regime,
            quantity=self.config.default_quantity,
            legs=tuple(legs),
            estimated_credit=credit,
            estimated_debit=debit,
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


def _build_legs(
    strategy: StrategyType,
    chain: list[OptionContractQuote],
    spot: float,
    quantity: int,
) -> tuple[list[OrderLeg], float | None, float | None]:
    calls = sorted((c for c in chain if c.option_type is OptionType.CALL), key=lambda c: c.strike)
    puts = sorted((p for p in chain if p.option_type is OptionType.PUT), key=lambda p: p.strike)
    if strategy is StrategyType.BULL_CALL_DEBIT_SPREAD:
        buy, sell = _nearest_above(calls, spot)
        return _two_leg_debit(buy, sell, buy_side=OrderSide.BUY, sell_side=OrderSide.SELL, quantity=quantity)
    if strategy is StrategyType.BEAR_PUT_DEBIT_SPREAD:
        buy, sell = _nearest_below(puts, spot)
        return _two_leg_debit(buy, sell, buy_side=OrderSide.BUY, sell_side=OrderSide.SELL, quantity=quantity)
    if strategy is StrategyType.BULL_PUT_CREDIT_SPREAD:
        sell, buy = _nearest_below(puts, spot)
        return _two_leg_credit(sell, buy, quantity=quantity)
    if strategy is StrategyType.BEAR_CALL_CREDIT_SPREAD:
        sell, buy = _nearest_above(calls, spot)
        return _two_leg_credit(sell, buy, quantity=quantity)
    if strategy is StrategyType.SHORT_IRON_CONDOR:
        put_sell, put_buy = _nearest_below(puts, spot)
        call_sell, call_buy = _nearest_above(calls, spot)
        legs = [
            _leg(put_buy, OrderSide.BUY, quantity),
            _leg(put_sell, OrderSide.SELL, quantity),
            _leg(call_sell, OrderSide.SELL, quantity),
            _leg(call_buy, OrderSide.BUY, quantity),
        ]
        credit = round((_mid(put_sell) + _mid(call_sell) - _mid(put_buy) - _mid(call_buy)), 2)
        return legs, max(credit, 0.01), None
    near_call, far_call = _nearest_above(calls, spot)
    legs = [_leg(near_call, OrderSide.BUY, quantity), _leg(far_call, OrderSide.SELL, quantity)]
    return legs, None, round(max(_mid(near_call) - _mid(far_call), 0.01), 2)


def _nearest_above(
    contracts: list[OptionContractQuote], spot: float
) -> tuple[OptionContractQuote, OptionContractQuote]:
    above = [contract for contract in contracts if contract.strike >= spot]
    candidates = above if len(above) >= 2 else contracts[-2:]
    if len(candidates) < 2:
        raise ValueError("Need at least two option contracts above spot")
    return candidates[0], candidates[1]


def _nearest_below(
    contracts: list[OptionContractQuote], spot: float
) -> tuple[OptionContractQuote, OptionContractQuote]:
    below = [contract for contract in contracts if contract.strike <= spot]
    candidates = below[-2:] if len(below) >= 2 else contracts[:2]
    if len(candidates) < 2:
        raise ValueError("Need at least two option contracts below spot")
    closer = candidates[-1]
    farther = candidates[-2]
    return closer, farther


def _two_leg_debit(
    buy: OptionContractQuote,
    sell: OptionContractQuote,
    *,
    buy_side: OrderSide,
    sell_side: OrderSide,
    quantity: int,
) -> tuple[list[OrderLeg], float | None, float | None]:
    legs = [_leg(buy, buy_side, quantity), _leg(sell, sell_side, quantity)]
    debit = round(max(_mid(buy) - _mid(sell), 0.01), 2)
    return legs, None, debit


def _two_leg_credit(
    sell: OptionContractQuote, buy: OptionContractQuote, *, quantity: int
) -> tuple[list[OrderLeg], float | None, float | None]:
    legs = [_leg(sell, OrderSide.SELL, quantity), _leg(buy, OrderSide.BUY, quantity)]
    credit = round(max(_mid(sell) - _mid(buy), 0.01), 2)
    return legs, credit, None


def _leg(option: OptionContractQuote, side: OrderSide, quantity: int) -> OrderLeg:
    return OrderLeg(
        contract_symbol=option.symbol,
        side=side,
        option_type=option.option_type,
        strike=option.strike,
        expiration_date=option.expiration_date,
        quantity=quantity,
    )


def _mid(option: OptionContractQuote) -> float:
    return option.mid if option.mid is not None else option.last or 0.0


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
