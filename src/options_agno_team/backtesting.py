"""Historical replay backtesting for the deterministic trading pipeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from options_agno_team.adapters.base import MarketDataAdapter, PriceCallback
from options_agno_team.config import AppConfig
from options_agno_team.features import FeatureEngine
from options_agno_team.models import (
    BacktestReport,
    BacktestTrade,
    DirectionalBias,
    NormalizedBar,
    NormalizedQuote,
    OptionContractQuote,
    StrategyProposal,
    StrategyType,
)
from options_agno_team.regime import RegimeEngine
from options_agno_team.risk import RiskEngine
from options_agno_team.strategy import StrategyEngine


class BacktestService:
    def __init__(
        self,
        adapter: MarketDataAdapter,
        config: AppConfig | None = None,
        *,
        feature_engine: FeatureEngine | None = None,
        regime_engine: RegimeEngine | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or AppConfig()
        self.feature_engine = feature_engine or FeatureEngine()
        self.regime_engine = regime_engine or RegimeEngine()

    def run(
        self,
        symbols: list[str],
        *,
        lookback: int = 180,
        min_lookback: int = 60,
        holding_period: int = 10,
        step: int = 5,
    ) -> BacktestReport:
        trades: list[BacktestTrade] = []
        started_at: datetime | None = None
        ended_at: datetime | None = None
        for raw_symbol in symbols:
            symbol = raw_symbol.upper()
            bars = self.adapter.get_bars(symbol, lookback=lookback)
            if len(bars) <= min_lookback + holding_period:
                continue
            started_at = min(started_at or bars[0].timestamp, bars[0].timestamp)
            ended_at = max(ended_at or bars[-1].timestamp, bars[-1].timestamp)
            trades.extend(
                self._replay_symbol(
                    symbol,
                    bars,
                    min_lookback=min_lookback,
                    holding_period=holding_period,
                    step=step,
                )
            )

        approved = [trade for trade in trades if trade.approved]
        report_key = f"{symbols}:{lookback}:{min_lookback}:{holding_period}:{step}:{len(trades)}"
        now = datetime.now(timezone.utc)
        return BacktestReport(
            report_id=str(uuid5(NAMESPACE_URL, f"backtest:{report_key}:{now.isoformat()}")),
            symbols=tuple(symbol.upper() for symbol in symbols),
            started_at=started_at or now,
            ended_at=ended_at or now,
            lookback=lookback,
            min_lookback=min_lookback,
            holding_period=holding_period,
            step=step,
            trades=tuple(trades),
            win_rate=_win_rate(approved),
            max_drawdown=_max_drawdown(approved),
            average_return=round(mean([trade.strategy_return for trade in approved]), 6)
            if approved
            else 0.0,
            regime_accuracy=_regime_accuracy(approved),
            strategy_performance=_group_performance(approved, key=lambda trade: trade.strategy_type.value),
            symbol_performance=_group_performance(approved, key=lambda trade: trade.symbol),
            regime_thesis_performance=_group_performance(approved, key=_regime_thesis_key),
            regime_thesis_insights=_performance_insights(
                _group_performance(approved, key=_regime_thesis_key),
                average_key="average_return",
            ),
        )

    def _replay_symbol(
        self,
        symbol: str,
        bars: list[NormalizedBar],
        *,
        min_lookback: int,
        holding_period: int,
        step: int,
    ) -> list[BacktestTrade]:
        trades: list[BacktestTrade] = []
        last_entry_index = len(bars) - holding_period - 1
        for entry_index in range(min_lookback, last_entry_index + 1, step):
            exit_index = entry_index + holding_period
            window = bars[: entry_index + 1]
            replay_adapter = _ReplayMarketDataAdapter(self.adapter, {symbol: window})
            chain = replay_adapter.get_option_chain(symbol)
            features = self.feature_engine.build(symbol, window, option_chain=chain)
            regime = self.regime_engine.classify(features)
            proposal = StrategyEngine(replay_adapter, self.config).propose(regime)
            risk = RiskEngine(replay_adapter, self.config).evaluate(proposal)
            trades.append(
                _trade_from_replay(
                    proposal,
                    entry_bar=bars[entry_index],
                    exit_bar=bars[exit_index],
                    approved=risk.approved,
                )
            )
        return trades


class _ReplayMarketDataAdapter:
    def __init__(
        self,
        base: MarketDataAdapter,
        bars_by_symbol: dict[str, list[NormalizedBar]],
    ) -> None:
        self.base = base
        self.bars_by_symbol = {symbol.upper(): bars for symbol, bars in bars_by_symbol.items()}

    def get_bars(self, symbol: str, *, lookback: int = 120, interval: str = "1d") -> list[NormalizedBar]:
        bars = self.bars_by_symbol[symbol.upper()]
        return bars[-lookback:]

    def get_quotes(self, symbols: list[str]) -> dict[str, NormalizedQuote]:
        quotes: dict[str, NormalizedQuote] = {}
        for raw_symbol in symbols:
            symbol = raw_symbol.upper()
            bars = self.bars_by_symbol[symbol]
            last = bars[-1].close
            quotes[symbol] = NormalizedQuote(
                symbol=symbol,
                timestamp=bars[-1].timestamp,
                bid=round(last - 0.02, 2),
                ask=round(last + 0.02, 2),
                last=round(last, 2),
                volume=bars[-1].volume,
                source="backtest",
            )
        return quotes

    def get_option_expirations(self, symbol: str) -> list[str]:
        replay_date = self.bars_by_symbol[symbol.upper()][-1].timestamp.date()
        return [
            (replay_date + timedelta(days=30)).isoformat(),
            (replay_date + timedelta(days=58)).isoformat(),
        ]

    def get_option_chain(
        self, symbol: str, *, expiration_date: str | None = None
    ) -> list[OptionContractQuote]:
        if expiration_date is None:
            chain: list[OptionContractQuote] = []
            for expiration in self.get_option_expirations(symbol):
                chain.extend(self.base.get_option_chain(symbol, expiration_date=expiration))
            return chain
        return self.base.get_option_chain(symbol, expiration_date=expiration_date)

    def get_option_greeks(self, osi_symbols: list[str]) -> dict[str, dict[str, float | None]]:
        return self.base.get_option_greeks(osi_symbols)

    def get_account(self) -> dict[str, Any]:
        return self.base.get_account()

    def get_positions(self) -> list[dict[str, Any]]:
        return self.base.get_positions()

    def subscribe_prices(
        self, symbols: list[str], callback: PriceCallback, *, interval_seconds: float = 5.0
    ) -> str:
        for quote in self.get_quotes(symbols).values():
            callback(quote)
        return "backtest-replay"


def _trade_from_replay(
    proposal: StrategyProposal,
    *,
    entry_bar: NormalizedBar,
    exit_bar: NormalizedBar,
    approved: bool,
) -> BacktestTrade:
    underlying_return = exit_bar.close / entry_bar.close - 1 if entry_bar.close else 0.0
    strategy_return = _strategy_return(proposal.strategy_type, proposal.regime.directional_bias, underlying_return)
    if not approved:
        strategy_return = 0.0
    pnl = round(proposal.max_loss * strategy_return, 2)
    thesis_matched = _thesis_matched(proposal.regime.directional_bias, underlying_return)
    return BacktestTrade(
        proposal_id=proposal.proposal_id,
        symbol=proposal.symbol,
        strategy_type=proposal.strategy_type,
        entry_time=entry_bar.timestamp,
        exit_time=exit_bar.timestamp,
        entry_price=round(entry_bar.close, 4),
        exit_price=round(exit_bar.close, 4),
        underlying_return=round(underlying_return, 6),
        strategy_return=round(strategy_return, 6),
        pnl=pnl,
        max_loss=proposal.max_loss,
        approved=approved,
        regime_label=proposal.regime.regime_label,
        volatility_regime=proposal.regime.volatility_regime,
        directional_bias=proposal.regime.directional_bias,
        thesis_matched=thesis_matched,
        outcome="win" if pnl > 0 else "loss" if pnl < 0 else "flat",
        original_thesis=proposal.rationale,
        outcome_vs_thesis=_outcome_vs_thesis(thesis_matched, pnl),
    )


def _strategy_return(
    strategy: StrategyType, bias: DirectionalBias, underlying_return: float
) -> float:
    if strategy in {
        StrategyType.BULL_CALL_DEBIT_SPREAD,
        StrategyType.BULL_PUT_CREDIT_SPREAD,
    }:
        raw = underlying_return * 4
    elif strategy in {
        StrategyType.BEAR_PUT_DEBIT_SPREAD,
        StrategyType.BEAR_CALL_CREDIT_SPREAD,
    }:
        raw = -underlying_return * 4
    elif bias is DirectionalBias.NEUTRAL_CHOPPY:
        raw = 0.18 - abs(underlying_return) * 5
    else:
        raw = underlying_return * 2
    return max(-1.0, min(1.0, raw))


def _thesis_matched(bias: DirectionalBias, underlying_return: float) -> bool:
    if bias is DirectionalBias.BULLISH:
        return underlying_return > 0
    if bias is DirectionalBias.BEARISH:
        return underlying_return < 0
    return abs(underlying_return) <= 0.015


def _win_rate(trades: list[BacktestTrade]) -> float:
    if not trades:
        return 0.0
    return round(sum(1 for trade in trades if trade.pnl > 0) / len(trades), 4)


def _regime_accuracy(trades: list[BacktestTrade]) -> float:
    if not trades:
        return 0.0
    return round(sum(1 for trade in trades if trade.thesis_matched) / len(trades), 4)


def _max_drawdown(trades: list[BacktestTrade]) -> float:
    peak = 0.0
    equity = 0.0
    max_drawdown = 0.0
    for trade in trades:
        equity += trade.pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return round(max_drawdown, 2)


def _group_performance(
    trades: list[BacktestTrade], *, key: Any
) -> dict[str, dict[str, float]]:
    groups: dict[str, list[BacktestTrade]] = defaultdict(list)
    for trade in trades:
        groups[key(trade)].append(trade)
    return {
        group: {
            "trades": float(len(items)),
            "win_rate": _win_rate(items),
            "average_return": round(mean([item.strategy_return for item in items]), 6),
            "pnl": round(sum(item.pnl for item in items), 2),
        }
        for group, items in sorted(groups.items())
    }


def _regime_thesis_key(trade: BacktestTrade) -> str:
    return (
        f"{_strategy_phrase(trade.strategy_type)} in {trade.volatility_regime.value}-vol "
        f"{trade.directional_bias.value.replace('_', '-')} regimes on {trade.symbol}"
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


def _performance_insights(
    performance: dict[str, dict[str, float]], *, average_key: str
) -> tuple[str, ...]:
    insights: list[str] = []
    for key, stats in sorted(performance.items()):
        average_value = stats.get(average_key, 0.0)
        label = _performance_label(stats.get("win_rate", 0.0), average_value)
        insights.append(
            f"{key} {label}: win_rate={stats.get('win_rate', 0.0):.2f}, "
            f"{average_key}={average_value:.4f}, pnl={stats.get('pnl', 0.0):.2f} "
            f"over {int(stats.get('trades', 0.0))} trades."
        )
    return tuple(insights)


def _performance_label(win_rate: float, average_value: float) -> str:
    if win_rate >= 0.55 and average_value > 0:
        return "performed well"
    if win_rate <= 0.45 or average_value < 0:
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
