from __future__ import annotations

from regime_trader.schemas.learning import LearnedHeuristic, PerformanceMetric, TradeJournalEntry
from regime_trader.schemas.market import Position


class SharedMemoryReader:
    def __init__(
        self,
        *,
        journal: tuple[TradeJournalEntry, ...] = (),
        positions: tuple[Position, ...] = (),
        heuristics: tuple[LearnedHeuristic, ...] = (),
        performance: tuple[PerformanceMetric, ...] = (),
    ) -> None:
        self.journal = journal
        self.positions = positions
        self.heuristics = heuristics
        self.performance = performance

    def approved_heuristics(self) -> tuple[LearnedHeuristic, ...]:
        return tuple(heuristic for heuristic in self.heuristics if heuristic.approval_status == "approved")

    def trade_summaries(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "journal_id": entry.journal_id,
                "symbol": entry.symbol,
                "strategy_type": str(entry.strategy_type),
                "entry_regime_label": entry.entry_regime_label,
            }
            for entry in self.journal
        )
