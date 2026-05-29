from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from regime_trader.schemas.base import DataQualityIssue
from regime_trader.schemas.market import Bar, OptionChain


def validate_bar_history(
    bars: Sequence[Bar],
    *,
    min_count: int,
    max_age: timedelta | None = None,
    expected_interval: timedelta | None = None,
    now: datetime | None = None,
) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    if len(bars) < min_count:
        issues.append(
            DataQualityIssue(
                code="insufficient_bars",
                severity="error",
                message=f"expected at least {min_count} bars, got {len(bars)}",
                symbol=bars[0].symbol if bars else None,
            )
        )
    timestamps = [bar.timestamp for bar in bars]
    if timestamps != sorted(timestamps):
        issues.append(
            DataQualityIssue(
                code="out_of_order_bars",
                severity="error",
                message="bar timestamps are not sorted ascending",
                symbol=bars[0].symbol if bars else None,
            )
        )
    if expected_interval and len(timestamps) > 1:
        for previous, current in pairwise(timestamps):
            if current - previous > expected_interval * 1.5:
                issues.append(
                    DataQualityIssue(
                        code="missing_interval",
                        severity="warning",
                        message=f"gap detected between {previous.isoformat()} and {current.isoformat()}",
                        symbol=bars[0].symbol,
                    )
                )
                break
    current_time = now or datetime.now(tz=UTC)
    if max_age and bars and current_time - bars[-1].timestamp > max_age:
        issues.append(
            DataQualityIssue(
                code="stale_bars",
                severity="error",
                message=f"latest bar is older than {max_age}",
                symbol=bars[-1].symbol,
            )
        )
    for bar in bars:
        if min(bar.open, bar.high, bar.low, bar.close) <= Decimal("0"):
            issues.append(
                DataQualityIssue(
                    code="invalid_price",
                    severity="error",
                    message="bar contains non-positive price",
                    symbol=bar.symbol,
                    timestamp=bar.timestamp,
                )
            )
            break
    return tuple(issues)


def validate_option_chain(
    chain: OptionChain,
    *,
    max_age: timedelta,
    min_contracts: int = 1,
    now: datetime | None = None,
) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    current_time = now or datetime.now(tz=UTC)
    if current_time - chain.timestamp > max_age:
        issues.append(
            DataQualityIssue(
                code="stale_option_chain",
                severity="error",
                message=f"option chain is older than {max_age}",
                symbol=chain.underlying_symbol,
                timestamp=chain.timestamp,
            )
        )
    if len(chain.contracts) < min_contracts:
        issues.append(
            DataQualityIssue(
                code="empty_option_chain",
                severity="error",
                message="option chain has no usable contracts",
                symbol=chain.underlying_symbol,
            )
        )
    return tuple((*chain.quality_issues, *issues))
