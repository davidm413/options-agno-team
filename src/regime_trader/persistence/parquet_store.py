from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from regime_trader.schemas.market import Bar
from regime_trader.schemas.regime import FeatureVector


class ParquetStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bars(self, bars: Sequence[Bar]) -> Path:
        if not bars:
            raise ValueError("cannot write empty bar batch")
        symbol = bars[0].symbol
        path = self.root / "bars" / f"symbol={symbol}"
        path.mkdir(parents=True, exist_ok=True)
        output = path / "bars.parquet"
        frame = pd.DataFrame([bar.model_dump(mode="json") for bar in bars])
        frame.to_parquet(output, index=False)
        return output

    def write_feature_snapshot(self, vector: FeatureVector) -> Path:
        path = self.root / "features" / f"symbol={vector.symbol}"
        path.mkdir(parents=True, exist_ok=True)
        output = path / f"{vector.timestamp.strftime('%Y%m%dT%H%M%S')}.parquet"
        rows: list[dict[str, Any]] = [
            {
                "symbol": vector.symbol,
                "timestamp": vector.timestamp,
                "feature": feature.name,
                "value": feature.value,
                "input_window_ref": vector.input_window_ref,
                "feature_config_version": vector.feature_config_version,
                "model_version": vector.model_version,
            }
            for feature in vector.features
        ]
        pd.DataFrame(rows).to_parquet(output, index=False)
        return output

    def read_feature_snapshot(self, path: str | Path) -> pd.DataFrame:
        return pd.read_parquet(path)
