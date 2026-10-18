"""k blending, switch costs and per-series metrics. Pure functions, no file access."""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.macro_filter_backtest import config as cfg


def filter_activation(joined: pd.DataFrame, labels: tuple[str, ...]) -> tuple[np.ndarray, int]:
    """OR of the component labels; any unknown component leaves the filter inactive."""
    flags = joined[list(labels)].astype("boolean")
    missing = flags.isna().any(axis=1).to_numpy()
    active = flags.fillna(False).any(axis=1).to_numpy(dtype=bool) & ~missing
    return active, int(missing.sum())


def k_series(active: np.ndarray, k_filtered: float = cfg.K_FILTERED) -> np.ndarray:
    return np.where(np.asarray(active, dtype=bool), k_filtered, 1.0)


def switch_notional(k: np.ndarray, k_initial: float = cfg.K_INITIAL) -> np.ndarray:
    """Sum of absolute sleeve weight changes, as calculate_turnover's traded_notional.

    Moving |dk| from the portfolio sleeve to the WLS sleeve sells |dk| and buys |dk|.
    """
    previous = np.r_[k_initial, np.asarray(k, dtype=float)[:-1]]
    return 2.0 * np.abs(np.asarray(k, dtype=float) - previous)


def blend(
    portfolio: np.ndarray,
    benchmark: np.ndarray,
    k: np.ndarray,
    *,
    cost_bps: float = cfg.COST_BPS,
    k_initial: float = cfg.K_INITIAL,
) -> tuple[np.ndarray, np.ndarray]:
    """Period return k*portfolio + (1-k)*WLS minus the k-switch cost; returns (return, cost)."""
    k = np.asarray(k, dtype=float)
    cost = switch_notional(k, k_initial) * cost_bps / 10_000.0
    returns = k * np.asarray(portfolio, dtype=float) + (1.0 - k) * np.asarray(benchmark, float)
    return returns - cost, cost


def rotation(base_turnover: np.ndarray, k: np.ndarray, k_initial: float = cfg.K_INITIAL):
    """One-way turnover: portfolio turnover scaled by its sleeve, plus the sleeve switch."""
    k = np.asarray(k, dtype=float)
    return k * np.asarray(base_turnover, dtype=float) + switch_notional(k, k_initial) / 2.0


def information_ratio(active: np.ndarray) -> float:
    active = np.asarray(active, dtype=float)
    if len(active) < 2:
        return np.nan
    spread = active.std(ddof=1)
    if not np.isfinite(spread) or spread <= 0:
        return np.nan
    return float(active.mean() / spread * np.sqrt(cfg.PERIODS_PER_YEAR))


def information_ratio_rows(active: np.ndarray) -> np.ndarray:
    """Row-wise information ratio of a 2-D array (placebo and bootstrap draws)."""
    active = np.asarray(active, dtype=float)
    spread = active.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = active.mean(axis=1) / spread * np.sqrt(cfg.PERIODS_PER_YEAR)
    return np.where(spread > 0, ratio, np.nan)


def wealth(returns: np.ndarray) -> np.ndarray:
    """Wealth at each rebalancing date, initial wealth 1 included."""
    return np.r_[1.0, np.cumprod(1.0 + np.asarray(returns, dtype=float))]


def max_drawdown(path: np.ndarray) -> float:
    path = np.asarray(path, dtype=float)
    return float(np.min(path / np.maximum.accumulate(path) - 1.0))


def series_metrics(returns, benchmark, k, turnover) -> dict:
    returns, benchmark = np.asarray(returns, float), np.asarray(benchmark, float)
    active = returns - benchmark
    strategy_wealth, benchmark_wealth = wealth(returns), wealth(benchmark)
    relative = strategy_wealth / benchmark_wealth
    return {
        "periods": len(returns),
        "net_return": float(strategy_wealth[-1] - 1.0),
        "benchmark_return": float(benchmark_wealth[-1] - 1.0),
        "active_return_pp": float(strategy_wealth[-1] - benchmark_wealth[-1]),
        "relative_return": float(relative[-1] - 1.0),
        "mean_active_annualized": float(active.mean() * cfg.PERIODS_PER_YEAR),
        "tracking_error": float(active.std(ddof=1) * np.sqrt(cfg.PERIODS_PER_YEAR)),
        "information_ratio": information_ratio(active),
        "max_relative_drawdown": max_drawdown(relative),
        "hit_rate": float(np.mean(active > 0)),
        "mean_rotation": float(np.mean(rotation(turnover, k))),
        "filtered_periods": int(np.sum(np.asarray(k) < 1.0)),
        "switch_cost_total": float(np.sum(switch_notional(k)) * cfg.COST_BPS / 10_000.0),
    }
