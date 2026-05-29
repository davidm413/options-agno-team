"""Deterministic fixture adapter for local development and tests."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from options_agno_team.adapters.base import PriceCallback
from options_agno_team.models import NormalizedBar, NormalizedQuote, OptionContractQuote, OptionType


class FixtureMarketDataAdapter:
    def __init__(self, *, now: datetime | None = None) -> None:
        self.now = now or datetime(2026, 5, 28, 15, 30, tzinfo=timezone.utc)
        self._spots = {
            "SPY": 520.0,
            "QQQ": 455.0,
            "TSLA": 185.0,
            "NVDA": 125.0,
            "BULL": 100.0,
            "BEAR": 100.0,
            "CHOP": 100.0,
            "HIGHVOL": 100.0,
            "FLAT": 100.0,
        }
        self._account = {
            "account_id": "FIXTURE-ACCOUNT",
            "equity": 100_000.0,
            "buying_power": 50_000.0,
            "portfolio_delta": 0.02,
            "day_pnl": 0.0,
            "trades_today": 0,
        }
        self._positions = [
            {"symbol": "SPY", "quantity": 10, "delta": 0.01, "market_value": 5_200.0}
        ]

    def get_bars(self, symbol: str, *, lookback: int = 120, interval: str = "1d") -> list[NormalizedBar]:
        symbol = symbol.upper()
        scenario = _scenario_for(symbol)
        spot = self._spots.get(symbol, 100.0)
        closes = _build_close_series(spot=spot, lookback=lookback, scenario=scenario)
        bars: list[NormalizedBar] = []
        for index, close in enumerate(closes):
            timestamp = self.now - timedelta(days=len(closes) - index - 1)
            previous = closes[index - 1] if index else close
            high = max(close, previous) * 1.003
            low = min(close, previous) * 0.997
            bars.append(
                NormalizedBar(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=previous,
                    high=high,
                    low=low,
                    close=close,
                    volume=1_000_000 + index * 1000,
                    source="fixture",
                )
            )
        return bars

    def get_quotes(self, symbols: list[str]) -> dict[str, NormalizedQuote]:
        quotes: dict[str, NormalizedQuote] = {}
        for raw_symbol in symbols:
            symbol = raw_symbol.upper()
            bars = self.get_bars(symbol, lookback=3)
            last = bars[-1].close
            quotes[symbol] = NormalizedQuote(
                symbol=symbol,
                timestamp=self.now,
                bid=round(last - 0.02, 2),
                ask=round(last + 0.02, 2),
                last=round(last, 2),
                volume=bars[-1].volume,
                source="fixture",
            )
        return quotes

    def get_option_expirations(self, symbol: str) -> list[str]:
        first = self.now.date() + timedelta(days=30)
        second = self.now.date() + timedelta(days=58)
        return [first.isoformat(), second.isoformat()]

    def get_option_chain(
        self, symbol: str, *, expiration_date: str | None = None
    ) -> list[OptionContractQuote]:
        symbol = symbol.upper()
        spot = self.get_quotes([symbol])[symbol].last or self._spots.get(symbol, 100.0)
        expirations = self.get_option_expirations(symbol)
        dates = [expiration_date] if expiration_date else expirations
        chain: list[OptionContractQuote] = []
        for date_index, expiration in enumerate(dates):
            if expiration is None:
                continue
            days_factor = 1.0 + date_index * 0.08
            for strike in _strike_grid(spot):
                distance = abs(strike - spot) / max(spot, 1.0)
                base_iv = 0.22 + distance * 0.85 + date_index * 0.03
                call_mid = max(0.25, max(0.0, spot - strike) + spot * base_iv * 0.035 * days_factor)
                put_mid = max(0.25, max(0.0, strike - spot) + spot * (base_iv + 0.03) * 0.035)
                chain.append(
                    _option_quote(
                        underlying=symbol,
                        expiration=expiration,
                        option_type=OptionType.CALL,
                        strike=strike,
                        mid=round(call_mid, 2),
                        implied_volatility=round(base_iv, 4),
                        spot=spot,
                    )
                )
                chain.append(
                    _option_quote(
                        underlying=symbol,
                        expiration=expiration,
                        option_type=OptionType.PUT,
                        strike=strike,
                        mid=round(put_mid, 2),
                        implied_volatility=round(base_iv + 0.03, 4),
                        spot=spot,
                    )
                )
        return chain

    def get_option_greeks(self, osi_symbols: list[str]) -> dict[str, dict[str, float | None]]:
        all_options = {option.symbol: option for option in self.get_option_chain("SPY")}
        for symbol in self._spots:
            all_options.update({option.symbol: option for option in self.get_option_chain(symbol)})
        greeks: dict[str, dict[str, float | None]] = {}
        for symbol in osi_symbols:
            option = all_options.get(symbol)
            greeks[symbol] = {
                "delta": option.delta if option else None,
                "gamma": option.gamma if option else None,
                "theta": option.theta if option else None,
                "vega": option.vega if option else None,
                "rho": option.rho if option else None,
                "implied_volatility": option.implied_volatility if option else None,
            }
        return greeks

    def get_account(self) -> dict[str, Any]:
        return dict(self._account)

    def get_positions(self) -> list[dict[str, Any]]:
        return [dict(position) for position in self._positions]

    def subscribe_prices(
        self, symbols: list[str], callback: PriceCallback, *, interval_seconds: float = 5.0
    ) -> str:
        for quote in self.get_quotes(symbols).values():
            callback(quote)
        return f"fixture-{uuid4()}"


def _scenario_for(symbol: str) -> str:
    if symbol in {"BULL", "NVDA", "TSLA"}:
        return "bull"
    if symbol == "BEAR":
        return "bear"
    if symbol == "CHOP":
        return "chop"
    if symbol == "HIGHVOL":
        return "highvol"
    if symbol == "FLAT":
        return "flat"
    return "moderate_bull"


def _build_close_series(*, spot: float, lookback: int, scenario: str) -> list[float]:
    closes: list[float] = []
    start = spot
    for index in range(max(lookback, 2)):
        x = index / max(lookback - 1, 1)
        wave = math.sin(index / 3.0) * 0.003
        if scenario == "bull":
            value = start * (0.88 + 0.18 * x + wave)
        elif scenario == "bear":
            value = start * (1.12 - 0.18 * x + wave)
        elif scenario == "chop":
            value = start * (1.0 + math.sin(index / 2.0) * 0.015)
        elif scenario == "highvol":
            value = start * (0.92 + 0.16 * x + math.sin(index * 1.7) * 0.065)
        elif scenario == "flat":
            value = start
        else:
            value = start * (0.96 + 0.08 * x + wave)
        closes.append(round(max(value, 0.01), 4))
    return closes


def _strike_grid(spot: float) -> list[float]:
    step = 5.0 if spot < 250 else 10.0
    center = round(spot / step) * step
    return [round(center + step * offset, 2) for offset in range(-4, 5)]


def _option_quote(
    *,
    underlying: str,
    expiration: str,
    option_type: OptionType,
    strike: float,
    mid: float,
    implied_volatility: float,
    spot: float,
) -> OptionContractQuote:
    bid = max(0.01, round(mid - 0.05, 2))
    ask = round(mid + 0.05, 2)
    moneyness = (spot - strike) / max(spot, 1.0)
    if option_type is OptionType.CALL:
        delta = 0.45 + moneyness * 2.0
    else:
        delta = -0.45 + moneyness * 2.0
    delta = max(-0.95, min(0.95, delta))
    symbol = _make_osi(underlying, expiration, option_type, strike)
    return OptionContractQuote(
        symbol=symbol,
        underlying=underlying,
        expiration_date=expiration,
        option_type=option_type,
        strike=strike,
        bid=bid,
        ask=ask,
        last=mid,
        delta=round(delta, 4),
        gamma=0.04,
        theta=-0.03,
        vega=0.12,
        rho=0.01,
        implied_volatility=implied_volatility,
        volume=500,
        open_interest=2_000,
        source="fixture",
    )


def _make_osi(symbol: str, expiration_date: str, option_type: OptionType, strike: float) -> str:
    root = symbol.ljust(6)[:6]
    yy, mm, dd = expiration_date[2:4], expiration_date[5:7], expiration_date[8:10]
    cp = "C" if option_type is OptionType.CALL else "P"
    strike_value = int(round(strike * 1000))
    return f"{root}{yy}{mm}{dd}{cp}{strike_value:08d}"
