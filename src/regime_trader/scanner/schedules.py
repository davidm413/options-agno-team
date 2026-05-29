from __future__ import annotations

from dataclasses import dataclass

from regime_trader.scanner.service import MarketScanner, MarketScanResult


@dataclass(frozen=True)
class ScanSchedule:
    name: str
    cron: str
    description: str


DEFAULT_SCAN_SCHEDULES = (
    ScanSchedule("pre_market", "30 8 * * 1-5", "Pre-market scan before US regular session"),
    ScanSchedule("intraday", "*/30 9-15 * * 1-5", "Intraday scan on a 30 minute cadence"),
    ScanSchedule("end_of_day", "15 16 * * 1-5", "End-of-day scan after close"),
)


class ScheduledScanRunner:
    def __init__(self, scanner: MarketScanner) -> None:
        self.scanner = scanner

    def run(self, schedule: ScanSchedule) -> MarketScanResult:
        result = self.scanner.scan()
        return result.model_copy(update={"status": result.status, "created_at": result.created_at})
