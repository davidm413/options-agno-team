from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from regime_trader.schemas.market import OptionChain, OptionType


def _ivs(chain: OptionChain) -> list[float]:
    return [contract.implied_volatility for contract in chain.contracts if contract.implied_volatility is not None]


def implied_volatility_rank(current_iv: float, historical_iv_values: Sequence[float]) -> float:
    if not historical_iv_values:
        return 0.0
    low = min(historical_iv_values)
    high = max(historical_iv_values)
    if high == low:
        return 0.0
    return max(0.0, min(1.0, (current_iv - low) / (high - low)))


def chain_average_iv(chain: OptionChain) -> float | None:
    values = _ivs(chain)
    if not values:
        return None
    return float(sum(values) / len(values))


def skew(chain: OptionChain) -> float | None:
    calls = [
        contract.implied_volatility
        for contract in chain.contracts
        if contract.option_type == OptionType.CALL and contract.implied_volatility is not None
    ]
    puts = [
        contract.implied_volatility
        for contract in chain.contracts
        if contract.option_type == OptionType.PUT and contract.implied_volatility is not None
    ]
    if not calls or not puts:
        return None
    return float((sum(puts) / len(puts)) - (sum(calls) / len(calls)))


def term_structure_slope(chains: Sequence[OptionChain]) -> float | None:
    by_expiration: list[tuple[date, float]] = []
    for chain in chains:
        avg = chain_average_iv(chain)
        if chain.expiration and avg is not None:
            by_expiration.append((chain.expiration, avg))
    if len(by_expiration) < 2:
        return None
    by_expiration.sort(key=lambda item: item[0])
    first, last = by_expiration[0], by_expiration[-1]
    days = max((last[0] - first[0]).days, 1)
    return float((last[1] - first[1]) / days)


def option_strength_metrics(chain: OptionChain) -> dict[str, float]:
    contracts = list(chain.contracts)
    if not contracts:
        return {"liquidity_score": 0.0, "spread_score": 0.0}
    liquid = [contract for contract in contracts if (contract.open_interest or 0) > 0 or (contract.volume or 0) > 0]
    spreads = [
        float(contract.spread_width)
        for contract in contracts
        if contract.spread_width is not None and contract.mid_price not in {None, 0}
    ]
    avg_spread = sum(spreads) / len(spreads) if spreads else 1.0
    return {
        "liquidity_score": len(liquid) / len(contracts),
        "spread_score": max(0.0, 1.0 - min(avg_spread, 1.0)),
    }
