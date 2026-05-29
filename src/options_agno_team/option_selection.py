"""Contract selection rules for options strategy construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import inf, log1p

from options_agno_team.adapters.base import MarketDataAdapter
from options_agno_team.config import AppConfig
from options_agno_team.models import (
    OptionContractQuote,
    OptionType,
    OrderLeg,
    OrderSide,
    StrategyType,
)


@dataclass(frozen=True)
class OptionSelection:
    legs: tuple[OrderLeg, ...]
    estimated_credit: float | None
    estimated_debit: float | None
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class _SpreadCandidate:
    first: OptionContractQuote
    second: OptionContractQuote
    net_price: float
    score: float
    width: float
    first_delta: float
    second_delta: float
    bid_ask_pct: float
    liquidity_score: float
    min_open_interest: int | None
    min_volume: int | None


class OptionSelector:
    """Select option contracts with deterministic liquidity and structure gates."""

    def __init__(self, adapter: MarketDataAdapter, config: AppConfig | None = None) -> None:
        self.adapter = adapter
        self.config = config or AppConfig()

    def select(
        self,
        strategy: StrategyType,
        symbol: str,
        *,
        spot: float,
        quantity: int,
        as_of: datetime | None = None,
        iv_rank: float | None = None,
    ) -> OptionSelection:
        timestamp = as_of or datetime.now(timezone.utc)
        self._validate_iv_rank(iv_rank)
        if strategy is StrategyType.CALENDAR_SPREAD:
            return self._select_calendar(
                symbol,
                spot=spot,
                quantity=quantity,
                as_of=timestamp,
                iv_rank=iv_rank,
            )

        failures: list[str] = []
        for expiration, dte in self._ranked_expirations(symbol, timestamp.date()):
            chain = self.adapter.get_option_chain(symbol, expiration_date=expiration)
            liquid_chain = [contract for contract in chain if self._is_liquid(contract)]
            if not liquid_chain:
                failures.append(f"{expiration}: no contracts passed liquidity gates")
                continue
            try:
                selection = self._select_from_chain(
                    strategy,
                    liquid_chain,
                    spot=spot,
                    quantity=quantity,
                    expiration=expiration,
                    dte=dte,
                    iv_rank=iv_rank,
                )
            except ValueError as exc:
                failures.append(f"{expiration}: {exc}")
                continue
            return selection
        raise ValueError(f"No selectable option spread for {symbol} {strategy.value}: {failures}")

    def _select_from_chain(
        self,
        strategy: StrategyType,
        chain: list[OptionContractQuote],
        *,
        spot: float,
        quantity: int,
        expiration: str,
        dte: int,
        iv_rank: float | None,
    ) -> OptionSelection:
        calls = sorted((c for c in chain if c.option_type is OptionType.CALL), key=lambda c: c.strike)
        puts = sorted((p for p in chain if p.option_type is OptionType.PUT), key=lambda p: p.strike)

        if strategy is StrategyType.BULL_CALL_DEBIT_SPREAD:
            candidate = self._best_debit_spread(
                calls,
                spot=spot,
                first_above_second=False,
                first_target=self.config.option_target_long_delta,
                second_target=self.config.option_target_short_delta,
                strategy=strategy,
                iv_rank=iv_rank,
            )
            legs: tuple[OrderLeg, ...] = (
                _leg(candidate.first, OrderSide.BUY, quantity),
                _leg(candidate.second, OrderSide.SELL, quantity),
            )
            return self._selection(legs, None, candidate.net_price, candidate, expiration, dte, iv_rank)

        if strategy is StrategyType.BEAR_PUT_DEBIT_SPREAD:
            candidate = self._best_debit_spread(
                puts,
                spot=spot,
                first_above_second=True,
                first_target=self.config.option_target_long_delta,
                second_target=self.config.option_target_short_delta,
                strategy=strategy,
                iv_rank=iv_rank,
            )
            legs = (
                _leg(candidate.first, OrderSide.BUY, quantity),
                _leg(candidate.second, OrderSide.SELL, quantity),
            )
            return self._selection(legs, None, candidate.net_price, candidate, expiration, dte, iv_rank)

        if strategy is StrategyType.BULL_PUT_CREDIT_SPREAD:
            candidate = self._best_credit_spread(
                puts,
                spot=spot,
                first_above_second=True,
                first_target=self.config.option_target_short_delta,
                second_target=self.config.option_target_hedge_delta,
                strategy=strategy,
                iv_rank=iv_rank,
            )
            legs = (
                _leg(candidate.first, OrderSide.SELL, quantity),
                _leg(candidate.second, OrderSide.BUY, quantity),
            )
            return self._selection(legs, candidate.net_price, None, candidate, expiration, dte, iv_rank)

        if strategy is StrategyType.BEAR_CALL_CREDIT_SPREAD:
            candidate = self._best_credit_spread(
                calls,
                spot=spot,
                first_above_second=False,
                first_target=self.config.option_target_short_delta,
                second_target=self.config.option_target_hedge_delta,
                strategy=strategy,
                iv_rank=iv_rank,
            )
            legs = (
                _leg(candidate.first, OrderSide.SELL, quantity),
                _leg(candidate.second, OrderSide.BUY, quantity),
            )
            return self._selection(legs, candidate.net_price, None, candidate, expiration, dte, iv_rank)

        if strategy is StrategyType.SHORT_IRON_CONDOR:
            put_candidate = self._best_credit_spread(
                puts,
                spot=spot,
                first_above_second=True,
                first_target=self.config.option_target_short_delta,
                second_target=self.config.option_target_hedge_delta,
                strategy=strategy,
                iv_rank=iv_rank,
            )
            call_candidate = self._best_credit_spread(
                calls,
                spot=spot,
                first_above_second=False,
                first_target=self.config.option_target_short_delta,
                second_target=self.config.option_target_hedge_delta,
                strategy=strategy,
                iv_rank=iv_rank,
            )
            legs = (
                _leg(put_candidate.second, OrderSide.BUY, quantity),
                _leg(put_candidate.first, OrderSide.SELL, quantity),
                _leg(call_candidate.first, OrderSide.SELL, quantity),
                _leg(call_candidate.second, OrderSide.BUY, quantity),
            )
            credit = round(put_candidate.net_price + call_candidate.net_price, 2)
            wider = put_candidate if put_candidate.width >= call_candidate.width else call_candidate
            return self._selection(legs, credit, None, wider, expiration, dte, iv_rank)

        raise ValueError(f"Unsupported strategy {strategy.value}")

    def _select_calendar(
        self,
        symbol: str,
        *,
        spot: float,
        quantity: int,
        as_of: datetime,
        iv_rank: float | None,
    ) -> OptionSelection:
        expirations = self._ranked_expirations(symbol, as_of.date())
        if len(expirations) < 2:
            raise ValueError("Calendar spreads need at least two expirations")
        chronological_expirations = sorted(expirations, key=lambda item: item[1])
        near_expiration, near_dte = chronological_expirations[0]
        far_expiration, far_dte = chronological_expirations[1]
        near = [c for c in self.adapter.get_option_chain(symbol, expiration_date=near_expiration) if self._is_liquid(c)]
        far = [c for c in self.adapter.get_option_chain(symbol, expiration_date=far_expiration) if self._is_liquid(c)]
        near_calls = [c for c in near if c.option_type is OptionType.CALL]
        far_calls = [c for c in far if c.option_type is OptionType.CALL]
        pairs = [
            (near_contract, far_contract)
            for near_contract in near_calls
            for far_contract in far_calls
            if near_contract.strike == far_contract.strike
        ]
        if not pairs:
            raise ValueError("No liquid same-strike calendar candidates")
        near_contract, far_contract = min(
            pairs,
            key=lambda pair: (
                _moneyness_penalty(pair[0], spot) * 3
                + abs(_delta_abs(pair[0], spot) - 0.50) * 2
                + self._contract_liquidity_score(pair[0])
                + self._contract_liquidity_score(pair[1])
                + self._calendar_iv_penalty(pair[0], pair[1], iv_rank)
            ),
        )
        debit = round(max(_mid(far_contract) - _mid(near_contract), 0.01), 2)
        legs = (
            _leg(near_contract, OrderSide.SELL, quantity),
            _leg(far_contract, OrderSide.BUY, quantity),
        )
        rationale: tuple[str, ...] = (
            f"near_expiration={near_expiration}",
            f"far_expiration={far_expiration}",
            f"dte_pair={near_dte}/{far_dte}",
            f"strike={near_contract.strike:.2f}",
            f"net_debit={debit:.2f}",
            f"bid_ask_pct={max(_bid_ask_pct(near_contract), _bid_ask_pct(far_contract)):.2f}",
            f"min_open_interest={_format_optional_int(_min_known_int(near_contract.open_interest, far_contract.open_interest))}",
        )
        if iv_rank is not None:
            rationale = (*rationale, f"iv_rank={iv_rank:.1f}")
        return OptionSelection(legs=legs, estimated_credit=None, estimated_debit=debit, rationale=rationale)

    def _best_debit_spread(
        self,
        contracts: list[OptionContractQuote],
        *,
        spot: float,
        first_above_second: bool,
        first_target: float,
        second_target: float,
        strategy: StrategyType,
        iv_rank: float | None,
    ) -> _SpreadCandidate:
        return self._best_spread(
            contracts,
            spot=spot,
            first_above_second=first_above_second,
            first_target=first_target,
            second_target=second_target,
            price_direction="debit",
            strategy=strategy,
            iv_rank=iv_rank,
        )

    def _best_credit_spread(
        self,
        contracts: list[OptionContractQuote],
        *,
        spot: float,
        first_above_second: bool,
        first_target: float,
        second_target: float,
        strategy: StrategyType,
        iv_rank: float | None,
    ) -> _SpreadCandidate:
        return self._best_spread(
            contracts,
            spot=spot,
            first_above_second=first_above_second,
            first_target=first_target,
            second_target=second_target,
            price_direction="credit",
            strategy=strategy,
            iv_rank=iv_rank,
        )

    def _best_spread(
        self,
        contracts: list[OptionContractQuote],
        *,
        spot: float,
        first_above_second: bool,
        first_target: float,
        second_target: float,
        price_direction: str,
        strategy: StrategyType,
        iv_rank: float | None,
    ) -> _SpreadCandidate:
        if len(contracts) < 2:
            raise ValueError("Need at least two contracts")
        min_width = max(
            self.config.option_min_spread_width,
            spot * self.config.option_min_spread_width_pct,
        )
        max_width = max(1.0, spot * self.config.option_max_spread_width_pct)
        preferred_width = max(1.0, spot * self.config.option_preferred_spread_width_pct)
        best: _SpreadCandidate | None = None
        for first in contracts:
            for second in contracts:
                if first.symbol == second.symbol:
                    continue
                valid_orientation = first.strike > second.strike if first_above_second else first.strike < second.strike
                if not valid_orientation:
                    continue
                width = abs(first.strike - second.strike)
                if width < min_width or width > max_width:
                    continue
                first_mid = _mid(first)
                second_mid = _mid(second)
                net = first_mid - second_mid
                if net <= 0 or net >= width:
                    continue
                first_delta = _delta_abs(first, spot)
                second_delta = _delta_abs(second, spot)
                liquidity_score = (
                    self._contract_liquidity_score(first)
                    + self._contract_liquidity_score(second)
                )
                bid_ask_pct = max(_bid_ask_pct(first), _bid_ask_pct(second))
                score = (
                    abs(first_delta - first_target) * 4
                    + abs(second_delta - second_target) * 4
                    + abs(width - preferred_width) / preferred_width
                    + liquidity_score
                    + bid_ask_pct
                    + self._spread_iv_penalty(strategy, iv_rank, first, second)
                    + _moneyness_penalty(first, spot)
                    + _moneyness_penalty(second, spot) * 0.5
                )
                candidate = _SpreadCandidate(
                    first=first,
                    second=second,
                    net_price=round(net, 2),
                    score=round(score, 6),
                    width=round(width, 2),
                    first_delta=round(first_delta, 4),
                    second_delta=round(second_delta, 4),
                    bid_ask_pct=round(bid_ask_pct, 6),
                    liquidity_score=round(liquidity_score, 6),
                    min_open_interest=_min_known_int(first.open_interest, second.open_interest),
                    min_volume=_min_known_int(first.volume, second.volume),
                )
                if best is None or candidate.score < best.score:
                    best = candidate
        if best is None:
            raise ValueError("No positive-price spread passed width and strike constraints")
        return best

    def _selection(
        self,
        legs: tuple[OrderLeg, ...],
        credit: float | None,
        debit: float | None,
        candidate: _SpreadCandidate,
        expiration: str,
        dte: int,
        iv_rank: float | None,
    ) -> OptionSelection:
        price_label = f"net_credit={credit:.2f}" if credit is not None else f"net_debit={debit:.2f}"
        rationale = [
            f"expiration={expiration}",
            f"dte={dte}",
            f"spread_width={candidate.width:.2f}",
            price_label,
            f"score={candidate.score:.3f}",
            f"delta_pair={candidate.first_delta:.2f}/{candidate.second_delta:.2f}",
            f"bid_ask_pct={candidate.bid_ask_pct:.2f}",
            f"liquidity_score={candidate.liquidity_score:.3f}",
            f"min_open_interest={_format_optional_int(candidate.min_open_interest)}",
            f"min_volume={_format_optional_int(candidate.min_volume)}",
            (
                f"liquidity=open_interest>={self.config.option_min_open_interest} "
                f"volume>={self.config.option_min_volume} "
                f"bid_ask_width<={self.config.option_max_bid_ask_width:.2f} "
                f"bid_ask_pct<={self.config.option_max_bid_ask_pct:.2f}"
            ),
        ]
        if iv_rank is not None:
            rationale.append(f"iv_rank={iv_rank:.1f}")
        return OptionSelection(
            legs=legs,
            estimated_credit=credit,
            estimated_debit=debit,
            rationale=tuple(rationale),
        )

    def _ranked_expirations(self, symbol: str, as_of: date) -> list[tuple[str, int]]:
        parsed: list[tuple[str, int]] = []
        for expiration in self.adapter.get_option_expirations(symbol):
            try:
                expiration_date = date.fromisoformat(expiration)
            except ValueError:
                continue
            dte = (expiration_date - as_of).days
            if dte > 0:
                parsed.append((expiration, dte))
        if not parsed:
            raise ValueError(f"No future option expirations for {symbol}")
        target_dte = (self.config.option_min_dte + self.config.option_max_dte) / 2
        in_window = [
            item
            for item in parsed
            if self.config.option_min_dte <= item[1] <= self.config.option_max_dte
        ]
        if not in_window:
            available = ", ".join(f"{expiration}:{dte}d" for expiration, dte in parsed)
            raise ValueError(
                f"No expirations inside configured DTE window "
                f"{self.config.option_min_dte}-{self.config.option_max_dte} for {symbol}; "
                f"available={available}"
            )
        return sorted(in_window, key=lambda item: (abs(item[1] - target_dte), item[1]))

    def _is_liquid(self, contract: OptionContractQuote) -> bool:
        if contract.bid is None or contract.ask is None or contract.ask < contract.bid:
            return False
        mid = _mid(contract)
        if mid <= 0:
            return False
        width = contract.ask - contract.bid
        if width > self.config.option_max_bid_ask_width:
            return False
        if width / mid > self.config.option_max_bid_ask_pct:
            return False
        if self.config.option_min_open_interest > 0 and (
            contract.open_interest is None
            or contract.open_interest < self.config.option_min_open_interest
        ):
            return False
        if self.config.option_min_volume > 0 and (
            contract.volume is None or contract.volume < self.config.option_min_volume
        ):
            return False
        return True

    def _validate_iv_rank(self, iv_rank: float | None) -> None:
        if iv_rank is None:
            return
        if not self.config.option_min_iv_rank <= iv_rank <= self.config.option_max_iv_rank:
            raise ValueError(
                f"iv_rank {iv_rank:.1f} outside configured range "
                f"{self.config.option_min_iv_rank:.1f}-{self.config.option_max_iv_rank:.1f}"
            )

    def _contract_liquidity_score(self, contract: OptionContractQuote) -> float:
        absolute_width_score = _bid_ask_width(contract) / max(
            self.config.option_max_bid_ask_width,
            0.01,
        )
        percent_width_score = _bid_ask_pct(contract) / max(
            self.config.option_max_bid_ask_pct,
            0.01,
        )
        return (
            absolute_width_score * 0.35
            + percent_width_score * 0.65
            + _depth_penalty(contract.open_interest, self.config.option_min_open_interest) * 0.9
            + _depth_penalty(contract.volume, self.config.option_min_volume) * 0.6
        )

    def _spread_iv_penalty(
        self,
        strategy: StrategyType,
        iv_rank: float | None,
        first: OptionContractQuote,
        second: OptionContractQuote,
    ) -> float:
        return _iv_rank_penalty(strategy, iv_rank) + _contract_iv_penalty(strategy, first, second)

    def _calendar_iv_penalty(
        self,
        near: OptionContractQuote,
        far: OptionContractQuote,
        iv_rank: float | None,
    ) -> float:
        rank_penalty = _iv_rank_penalty(StrategyType.CALENDAR_SPREAD, iv_rank)
        near_iv = near.implied_volatility
        far_iv = far.implied_volatility
        if near_iv is None or far_iv is None:
            return rank_penalty + 0.25
        backwardation_penalty = max(0.0, float(near_iv) - float(far_iv)) * 2
        return rank_penalty + backwardation_penalty


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
    if option.mid is not None:
        return float(option.mid)
    if option.last is not None:
        return float(option.last)
    return 0.0


def _delta_abs(option: OptionContractQuote, spot: float) -> float:
    if option.delta is not None:
        return abs(float(option.delta))
    if spot <= 0:
        return 0.5
    distance = abs(option.strike - spot) / spot
    return max(0.05, min(0.95, 0.5 - distance))


def _bid_ask_pct(option: OptionContractQuote) -> float:
    if option.bid is None or option.ask is None:
        return inf
    mid = _mid(option)
    if mid <= 0:
        return inf
    return max(0.0, float(option.ask) - float(option.bid)) / mid


def _bid_ask_width(option: OptionContractQuote) -> float:
    if option.bid is None or option.ask is None:
        return inf
    return max(0.0, float(option.ask) - float(option.bid))


def _moneyness_penalty(option: OptionContractQuote, spot: float) -> float:
    if spot <= 0:
        return 0.0
    return abs(option.strike - spot) / spot


def _depth_penalty(value: int | None, minimum: int) -> float:
    if minimum <= 0:
        return 0.0
    if value is None or value <= 0:
        return 1.0
    depth_ratio = max(float(value) / minimum, 1.0)
    return 1.0 / (1.0 + log1p(depth_ratio))


def _iv_rank_penalty(strategy: StrategyType, iv_rank: float | None) -> float:
    if iv_rank is None:
        return 0.15
    targets = {
        StrategyType.BULL_CALL_DEBIT_SPREAD: 35.0,
        StrategyType.BEAR_PUT_DEBIT_SPREAD: 35.0,
        StrategyType.BULL_PUT_CREDIT_SPREAD: 65.0,
        StrategyType.BEAR_CALL_CREDIT_SPREAD: 65.0,
        StrategyType.SHORT_IRON_CONDOR: 70.0,
        StrategyType.CALENDAR_SPREAD: 50.0,
    }
    return abs(iv_rank - targets[strategy]) / 100


def _contract_iv_penalty(
    strategy: StrategyType,
    first: OptionContractQuote,
    second: OptionContractQuote,
) -> float:
    values = [
        float(option.implied_volatility)
        for option in (first, second)
        if option.implied_volatility is not None
    ]
    if not values:
        return 0.2
    average_iv = sum(values) / len(values)
    if strategy in {
        StrategyType.BULL_PUT_CREDIT_SPREAD,
        StrategyType.BEAR_CALL_CREDIT_SPREAD,
        StrategyType.SHORT_IRON_CONDOR,
    }:
        return max(0.0, 0.30 - average_iv)
    if strategy in {StrategyType.BULL_CALL_DEBIT_SPREAD, StrategyType.BEAR_PUT_DEBIT_SPREAD}:
        return max(0.0, average_iv - 0.55)
    return abs(average_iv - 0.35) * 0.5


def _min_known_int(first: int | None, second: int | None) -> int | None:
    values = [value for value in (first, second) if value is not None]
    return min(values) if values else None


def _format_optional_int(value: int | None) -> str:
    return "unknown" if value is None else str(value)
