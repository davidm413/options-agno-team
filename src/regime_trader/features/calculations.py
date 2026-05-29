from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def log_returns(prices: Sequence[float]) -> np.ndarray:
    values = np.asarray(prices, dtype=float)
    if len(values) < 2:
        return np.asarray([], dtype=float)
    if np.any(values <= 0):
        raise ValueError("prices must be positive to compute log returns")
    return np.diff(np.log(values))


def rolling_realized_volatility(returns: Sequence[float], window: int, *, annualization: int = 252) -> float:
    values = np.asarray(returns, dtype=float)
    if len(values) < window:
        raise ValueError("insufficient returns for realized volatility window")
    return float(np.std(values[-window:], ddof=1) * math.sqrt(annualization))


def momentum(prices: Sequence[float], window: int) -> float:
    values = np.asarray(prices, dtype=float)
    if len(values) <= window:
        raise ValueError("insufficient prices for momentum window")
    return float((values[-1] / values[-window - 1]) - 1.0)


def wasserstein_distance_1d(current: Sequence[float], baseline: Sequence[float]) -> float:
    current_values = np.sort(np.asarray(current, dtype=float))
    baseline_values = np.sort(np.asarray(baseline, dtype=float))
    if len(current_values) == 0 or len(baseline_values) == 0:
        raise ValueError("wasserstein inputs must be non-empty")
    points = max(len(current_values), len(baseline_values))
    quantiles = np.linspace(0, 1, points)
    current_q = np.quantile(current_values, quantiles)
    baseline_q = np.quantile(baseline_values, quantiles)
    return float(np.mean(np.abs(current_q - baseline_q)))


def entropy(values: Sequence[float], bins: int) -> float:
    data = np.asarray(values, dtype=float)
    if len(data) == 0:
        raise ValueError("entropy input must be non-empty")
    counts, _ = np.histogram(data, bins=bins)
    probabilities = counts[counts > 0] / counts.sum()
    return float(-np.sum(probabilities * np.log(probabilities)))


def split_baseline_current(values: Sequence[float], baseline_count: int) -> tuple[np.ndarray, np.ndarray]:
    data = np.asarray(values, dtype=float)
    if len(data) < baseline_count + 2:
        raise ValueError("insufficient values for baseline/current split")
    return data[:baseline_count], data[baseline_count:]
