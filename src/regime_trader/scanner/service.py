from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

from pydantic import Field

from regime_trader.config.models import AppConfig
from regime_trader.data.interfaces import MarketDataProvider
from regime_trader.data.validation import validate_bar_history, validate_option_chain
from regime_trader.regimes.service import RegimeService
from regime_trader.scanner.anomaly import AnomalyFlag, detect_anomalies
from regime_trader.scanner.ranking import opportunity_score
from regime_trader.scanner.universe import load_scan_universe
from regime_trader.schemas.base import DataQualityIssue, StrictModel, utc_now
from regime_trader.schemas.market import AssetClass
from regime_trader.schemas.regime import RegimeOutput


class SymbolScanResult(StrictModel):
    symbol: str
    status: str
    regime: RegimeOutput | None = None
    score: float = Field(default=0.0, ge=0, le=1)
    anomalies: tuple[AnomalyFlag, ...] = ()
    data_quality: tuple[DataQualityIssue, ...] = ()
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketScanResult(StrictModel):
    scan_id: str
    status: str
    created_at: str
    config_version: str
    asset_class: AssetClass | None = None
    results: tuple[SymbolScanResult, ...]


class MarketScanner:
    def __init__(self, config: AppConfig, provider: MarketDataProvider, regime_service: RegimeService) -> None:
        self.config = config
        self.provider = provider
        self.regime_service = regime_service

    def scan(
        self,
        *,
        symbols: tuple[str, ...] | None = None,
        asset_class: AssetClass | None = None,
    ) -> MarketScanResult:
        selected = load_scan_universe(self.config.universe, symbols=symbols, asset_class=asset_class)
        results = tuple(self._scan_symbol(symbol, asset_class=asset_class) for symbol in selected)
        healthy = [result for result in results if result.status == "ok"]
        ranked = tuple(sorted(results, key=lambda result: result.score, reverse=True))
        return MarketScanResult(
            scan_id=f"scan-{uuid4().hex}",
            status="ok" if healthy else "failed",
            created_at=utc_now().isoformat(),
            config_version=self.config.version,
            asset_class=asset_class,
            results=ranked,
        )

    def _scan_symbol(self, symbol: str, *, asset_class: AssetClass | None) -> SymbolScanResult:
        try:
            bars = tuple(
                self.provider.get_bars(
                    symbol,
                    interval="1d",
                    limit=self.config.features.lookback_bars,
                )
            )
            quality = validate_bar_history(bars, min_count=self.config.features.lookback_bars)
            option_chain = None
            if asset_class == AssetClass.OPTION or symbol in self.config.universe.option_underlyings:
                option_chain = self.provider.get_option_chain(symbol)
                quality = (
                    *quality,
                    *validate_option_chain(option_chain, max_age=timedelta(minutes=20)),
                )
            error_quality = [issue for issue in quality if issue.severity == "error"]
            if error_quality:
                return SymbolScanResult(
                    symbol=symbol,
                    status="data_quality_error",
                    data_quality=quality,
                    error="; ".join(issue.message for issue in error_quality),
                )
            regime = self.regime_service.detect(symbol, bars, option_chain=option_chain)
            anomalies = detect_anomalies(regime, self.config.regimes)
            score = opportunity_score(regime, anomalies, data_valid=True)
            return SymbolScanResult(
                symbol=symbol,
                status="ok",
                regime=regime,
                score=score,
                anomalies=anomalies,
                data_quality=quality,
            )
        except Exception as exc:
            return SymbolScanResult(symbol=symbol, status="error", error=str(exc), score=0.0)
