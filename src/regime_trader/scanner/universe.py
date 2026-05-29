from __future__ import annotations

from regime_trader.config.models import SymbolUniverseConfig
from regime_trader.schemas.market import AssetClass


def load_scan_universe(
    config: SymbolUniverseConfig,
    *,
    symbols: tuple[str, ...] | None = None,
    asset_class: AssetClass | None = None,
) -> tuple[str, ...]:
    selected = symbols if symbols else config.symbols_for(asset_class)
    return tuple(dict.fromkeys(symbol.upper() for symbol in selected))
