"""Trade reflection and performance grouping."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from uuid import NAMESPACE_URL, uuid5

from options_agno_team.adapters.base import MarketDataAdapter
from options_agno_team.execution import ProposalRepository
from options_agno_team.features import FeatureEngine
from options_agno_team.models import (
    LearningReport,
    PaperPosition,
    RegimeSnapshot,
    StrategyType,
    TradeReflection,
)
from options_agno_team.regime import RegimeEngine


class LearningService:
    def __init__(
        self,
        adapter: MarketDataAdapter,
        repository: ProposalRepository,
        *,
        feature_engine: FeatureEngine | None = None,
        regime_engine: RegimeEngine | None = None,
    ) -> None:
        self.adapter = adapter
        self.repository = repository
        self.feature_engine = feature_engine or FeatureEngine()
        self.regime_engine = regime_engine or RegimeEngine()

    def reflect_positions(self, *, open_only: bool = True) -> LearningReport:
        positions = self.repository.list_paper_positions(open_only=open_only)
        reflections = tuple(self._reflect(position) for position in positions)
        for reflection in reflections:
            self.repository.save_trade_reflection(reflection)
        generated_at = datetime.now(timezone.utc)
        performance_by_regime = _performance_by_regime_thesis(reflections)
        return LearningReport(
            report_id=str(uuid5(NAMESPACE_URL, f"learning:{generated_at.isoformat()}:{len(reflections)}")),
            generated_at=generated_at,
            reflections=reflections,
            performance_by_thesis=_performance_by_thesis(reflections),
            performance_by_regime_thesis=performance_by_regime,
            insights=_performance_insights(performance_by_regime),
        )

    def _reflect(self, position: PaperPosition) -> TradeReflection:
        proposal = self.repository.get_proposal(position.proposal_id)
        current_regime = self._current_regime(position.symbol)
        thesis_matched = current_regime.directional_bias is proposal.regime.directional_bias
        outcome = "winning" if position.unrealized_pnl > 0 else "losing" if position.unrealized_pnl < 0 else "flat"
        outcome_vs_thesis = _outcome_vs_thesis(thesis_matched, position.unrealized_pnl)
        observations = (
            f"{proposal.strategy_type.value} on {position.symbol}",
            f"original={proposal.regime.regime_label}",
            f"current={current_regime.regime_label}",
            f"pnl={position.unrealized_pnl:.2f}",
            "thesis_matched" if thesis_matched else "thesis_diverged",
            f"outcome_vs_thesis={outcome_vs_thesis}",
        )
        timestamp = datetime.now(timezone.utc)
        return TradeReflection(
            reflection_id=str(uuid5(NAMESPACE_URL, f"reflection:{position.position_id}:{timestamp.isoformat()}")),
            position_id=position.position_id,
            proposal_id=position.proposal_id,
            symbol=position.symbol,
            strategy_type=position.strategy_type,
            timestamp=timestamp,
            original_regime_label=proposal.regime.regime_label,
            current_regime_label=current_regime.regime_label,
            original_thesis=proposal.rationale,
            thesis_matched=thesis_matched,
            outcome=outcome,
            pnl=position.unrealized_pnl,
            observations=observations,
            original_volatility_regime=proposal.regime.volatility_regime,
            original_directional_bias=proposal.regime.directional_bias,
            current_volatility_regime=current_regime.volatility_regime,
            current_directional_bias=current_regime.directional_bias,
            outcome_vs_thesis=outcome_vs_thesis,
        )

    def _current_regime(self, symbol: str) -> RegimeSnapshot:
        bars = self.adapter.get_bars(symbol, lookback=120)
        chain = self.adapter.get_option_chain(symbol)
        features = self.feature_engine.build(symbol, bars, option_chain=chain)
        return self.regime_engine.classify(features)


def _performance_by_thesis(reflections: tuple[TradeReflection, ...]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[TradeReflection]] = defaultdict(list)
    for reflection in reflections:
        key = (
            f"{reflection.strategy_type.value} in {reflection.original_regime_label} "
            f"on {reflection.symbol}"
        )
        grouped[key].append(reflection)
    return {
        key: {
            "trades": float(len(items)),
            "win_rate": round(sum(1 for item in items if item.pnl > 0) / len(items), 4),
            "average_pnl": round(mean([item.pnl for item in items]), 2),
            "total_pnl": round(sum(item.pnl for item in items), 2),
            "thesis_match_rate": round(
                sum(1 for item in items if item.thesis_matched) / len(items),
                4,
            ),
        }
        for key, items in sorted(grouped.items())
    }


def _performance_by_regime_thesis(
    reflections: tuple[TradeReflection, ...]
) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[TradeReflection]] = defaultdict(list)
    for reflection in reflections:
        grouped[_regime_thesis_key(reflection)].append(reflection)
    return {
        key: {
            "trades": float(len(items)),
            "win_rate": round(sum(1 for item in items if item.pnl > 0) / len(items), 4),
            "average_pnl": round(mean([item.pnl for item in items]), 2),
            "total_pnl": round(sum(item.pnl for item in items), 2),
            "thesis_match_rate": round(
                sum(1 for item in items if item.thesis_matched) / len(items),
                4,
            ),
        }
        for key, items in sorted(grouped.items())
    }


def _regime_thesis_key(reflection: TradeReflection) -> str:
    return (
        f"{_strategy_phrase(reflection.strategy_type)} in "
        f"{reflection.original_volatility_regime.value}-vol "
        f"{reflection.original_directional_bias.value.replace('_', '-')} regimes "
        f"on {reflection.symbol}"
    )


def _strategy_phrase(strategy: StrategyType) -> str:
    phrases = {
        StrategyType.BULL_CALL_DEBIT_SPREAD: "bull call spreads",
        StrategyType.BEAR_PUT_DEBIT_SPREAD: "bear put spreads",
        StrategyType.BULL_PUT_CREDIT_SPREAD: "bull put credit spreads",
        StrategyType.BEAR_CALL_CREDIT_SPREAD: "bear call credit spreads",
        StrategyType.SHORT_IRON_CONDOR: "short iron condors",
        StrategyType.CALENDAR_SPREAD: "calendar spreads",
    }
    return phrases[strategy]


def _performance_insights(performance: dict[str, dict[str, float]]) -> tuple[str, ...]:
    insights: list[str] = []
    for key, stats in sorted(performance.items()):
        average_pnl = stats.get("average_pnl", 0.0)
        label = _performance_label(stats.get("win_rate", 0.0), average_pnl)
        insights.append(
            f"{key} {label}: win_rate={stats.get('win_rate', 0.0):.2f}, "
            f"average_pnl={average_pnl:.2f}, "
            f"thesis_match_rate={stats.get('thesis_match_rate', 0.0):.2f} "
            f"over {int(stats.get('trades', 0.0))} trades."
        )
    return tuple(insights)


def _performance_label(win_rate: float, average_pnl: float) -> str:
    if win_rate >= 0.55 and average_pnl > 0:
        return "performed well"
    if win_rate <= 0.45 or average_pnl < 0:
        return "performed poorly"
    return "were mixed"


def _outcome_vs_thesis(thesis_matched: bool, pnl: float) -> str:
    if thesis_matched and pnl > 0:
        return "thesis_confirmed_win"
    if thesis_matched:
        return "thesis_matched_without_profit"
    if pnl > 0:
        return "thesis_diverged_but_profitable"
    return "thesis_failed_loss"
