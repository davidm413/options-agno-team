from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from regime_trader.schemas.learning import PerformanceMetric, TradeJournalEntry


def performance_by_regime(
    entries: tuple[TradeJournalEntry, ...],
    *,
    min_sample_size: int = 10,
) -> tuple[PerformanceMetric, ...]:
    groups: dict[str, list[TradeJournalEntry]] = defaultdict(list)
    for entry in entries:
        key = f"{entry.symbol}:{entry.entry_regime_label}:{entry.strategy_type}"
        groups[key].append(entry)
    metrics: list[PerformanceMetric] = []
    for key, group in groups.items():
        closed = [entry for entry in group if entry.realized_pnl is not None]
        sample = len(closed)
        wins = [entry for entry in closed if entry.realized_pnl is not None and entry.realized_pnl > 0]
        total = sum((entry.realized_pnl or Decimal("0")) for entry in closed)
        metrics.append(
            PerformanceMetric(
                group_key=key,
                sample_size=sample,
                win_rate=(len(wins) / sample) if sample else None,
                average_return=(total / sample) if sample else None,
                max_drawdown=min((entry.realized_pnl or Decimal("0")) for entry in closed) if closed else None,
                risk_adjusted_return=float(total / sample) if sample else None,
                low_confidence=sample < min_sample_size,
            )
        )
    return tuple(metrics)
