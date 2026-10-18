"""Block placebo activations and paired moving-block bootstrap, fixed before results."""

from __future__ import annotations

import hashlib

import numpy as np

from research.macro_filter_backtest import config as cfg
from research.macro_filter_backtest.mechanics import blend, information_ratio_rows, k_series


def sub_seed(base: int, *identity) -> int:
    digest = hashlib.sha256(":".join(map(str, identity)).encode()).hexdigest()
    return (base + int(digest[:8], 16)) % (2**32)


def active_runs(active: np.ndarray) -> list[int]:
    runs, length = [], 0
    for flag in np.asarray(active, dtype=bool):
        if flag:
            length += 1
        elif length:
            runs.append(length)
            length = 0
    if length:
        runs.append(length)
    return runs


def placebo_activation(active: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Same count and same multiset of active run lengths, placed uniformly at random.

    Interior gaps keep at least one inactive period, so runs never merge.
    """
    n, runs = len(active), active_runs(active)
    if not runs:
        return np.zeros(n, dtype=bool)
    runs = list(rng.permutation(runs))
    m = len(runs)
    free = n - sum(runs) - (m - 1)
    bars = np.sort(rng.choice(free + m, size=m, replace=False))
    gaps = np.diff(np.r_[-1, bars, free + m]) - 1
    gaps[1:-1] += 1
    output = np.zeros(n, dtype=bool)
    position = 0
    for gap, run in zip(gaps[:-1], runs, strict=True):
        position += int(gap)
        output[position : position + run] = True
        position += run
    return output


def placebo_medians(per_offset: dict, reference_active: dict, *, seed: int, draws: int) -> tuple:
    """Median-over-offsets information ratio for each placebo draw.

    per_offset[offset] = (portfolio, benchmark); reference_active[offset] = boolean array.
    Returns (medians, frequencies) where frequencies[offset] lists the draw activation counts.
    """
    rng = np.random.default_rng(seed)
    offsets = sorted(per_offset)
    ratios = np.empty((draws, len(offsets)))
    counts = {offset: [] for offset in offsets}
    for draw in range(draws):
        for column, offset in enumerate(offsets):
            portfolio, benchmark = per_offset[offset]
            active = placebo_activation(reference_active[offset], rng)
            counts[offset].append(int(active.sum()))
            returns, _ = blend(portfolio, benchmark, k_series(active))
            ratios[draw, column] = information_ratio_rows((returns - benchmark)[None, :])[0]
    return np.median(ratios, axis=1), counts


def block_indices(n: int, replicates: int, block: int, rng: np.random.Generator) -> np.ndarray:
    blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(replicates, blocks))
    return (starts[:, :, None] + np.arange(block)).reshape(replicates, -1)[:, :n]


def paired_difference(
    variant_active: np.ndarray,
    base_active: np.ndarray,
    *,
    seed: int,
    replicates: int = cfg.BOOTSTRAP_REPLICATES,
    block: int = cfg.BOOTSTRAP_BLOCK,
    level: float = cfg.BOOTSTRAP_LEVEL,
) -> dict:
    """Percentile intervals of F - base for the information ratio and annualized mean active."""
    variant_active = np.asarray(variant_active, dtype=float)
    base_active = np.asarray(base_active, dtype=float)
    n = len(base_active)
    rng = np.random.default_rng(seed)
    indices = block_indices(n, replicates, block, rng)
    variant, base = variant_active[indices], base_active[indices]
    delta_ir = information_ratio_rows(variant) - information_ratio_rows(base)
    delta_mean = (variant.mean(axis=1) - base.mean(axis=1)) * cfg.PERIODS_PER_YEAR
    tail = (1.0 - level) / 2.0
    output = {}
    for name, values in (("delta_ir", delta_ir), ("delta_mean_active", delta_mean)):
        finite = values[np.isfinite(values)]
        low, high = np.quantile(finite, [tail, 1.0 - tail]) if len(finite) else (np.nan, np.nan)
        output[f"{name}_ci_low"], output[f"{name}_ci_high"] = float(low), float(high)
        output[f"{name}_valid"] = int(len(finite))
    return output


def percentile_position(value: float, distribution: np.ndarray) -> float:
    """Share of placebo draws strictly below the observed value, in percent."""
    distribution = np.asarray(distribution, dtype=float)
    return float(np.mean(distribution < value) * 100.0)


def criterion(medians: dict, placebo: np.ndarray) -> dict:
    """Preregistered F1 rule on median-over-offsets information ratios."""
    threshold = float(np.quantile(placebo, cfg.PLACEBO_QUANTILE))
    primary = medians[cfg.PRIMARY]
    checks = {
        "beats_base": bool(primary > medians["base"]),
        "beats_T": bool(primary > medians["T"]),
        "beats_placebo_q95": bool(primary > threshold),
    }
    return {**checks, "placebo_q95": threshold, "met": all(checks.values())}


def conclusion(met_by_ablation: dict) -> str:
    if all(met_by_ablation.values()):
        return "apport démontré selon le critère préenregistré"
    if met_by_ablation.get("with_news") and not met_by_ablation.get("without_news"):
        return "fragile : critère atteint seulement avec GPR/EPU"
    return "pas d'apport démontré"
