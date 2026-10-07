"""Joint asset/WLS risk, using the team's existing Ledoit-Wolf estimator."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.covariance import estimate_ledoit_wolf

BENCHMARK = "__WLS_BENCHMARK__"


@dataclass(frozen=True)
class RelativeRiskResult:
    assets: list[str]
    covariance_weekly: pd.DataFrame
    factor_weekly: np.ndarray
    shrinkage: float
    n_observations: int
    observation_start: str
    observation_end: str


def psd_factor(matrix: np.ndarray) -> np.ndarray:
    """Return F with F.T @ F = C, rejecting material PSD/symmetry errors.

    Clip only tiny negative eigenvalues from floating point, without adding a
    variance floor: exact replication must retain its zero-risk directions.
    """
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[0] != values.shape[1] or not np.isfinite(values).all():
        raise ValueError("Covariance must be finite and square.")
    scale = max(float(np.max(np.abs(values))), 1e-12)
    if not np.allclose(values, values.T, atol=scale * 1e-10, rtol=0):
        raise ValueError("Covariance must be symmetric.")
    eigenvalues, vectors = np.linalg.eigh((values + values.T) / 2)
    if eigenvalues.min() < -scale * 1e-9:
        raise ValueError("Joint covariance is not positive semidefinite.")
    return np.sqrt(np.maximum(eigenvalues, 0))[:, None] * vectors.T


def estimate_relative_risk(
    asset_returns: pd.DataFrame,
    benchmark_returns: pd.Series,
    *,
    min_observations: int = 40,
) -> RelativeRiskResult:
    """Estimate one joint covariance on exactly the same dates and USD units.

    No columns/rows may disappear inside covariance.py. Shrinkage introduces
    model risk: estimated TE need not equal historical sample TE.
    """
    if not isinstance(min_observations, int) or min_observations < 2:
        raise ValueError("min_observations must be an integer >= 2.")
    if not isinstance(asset_returns, pd.DataFrame) or asset_returns.empty:
        raise ValueError("Asset returns must be a nonempty DataFrame.")
    if (
        asset_returns.columns.has_duplicates
        or BENCHMARK in asset_returns
        or any(not isinstance(a, str) or not a.strip() for a in asset_returns.columns)
        or not isinstance(asset_returns.index, pd.DatetimeIndex)
        or asset_returns.index.hasnans
        or asset_returns.index.has_duplicates
        or not asset_returns.index.is_monotonic_increasing
        or asset_returns.index.tz is not None
        or not asset_returns.index.equals(asset_returns.index.normalize())
        or not (asset_returns.index.dayofweek == 4).all()
    ):
        raise ValueError("Require unique asset identifiers and sorted Friday observations.")
    if not isinstance(benchmark_returns, pd.Series) or not asset_returns.index.equals(
        benchmark_returns.index
    ):
        raise ValueError("Asset and WLS return dates must match exactly.")
    joint = asset_returns.astype(float).copy()
    joint[BENCHMARK] = benchmark_returns.astype(float)
    if not np.isfinite(joint.to_numpy()).all() or (joint < -1).any().any():
        raise ValueError("Require finite simple returns >= -1; no hidden row/asset removal.")
    covariance = estimate_ledoit_wolf(joint, min_observations=min_observations)
    if covariance.assets != list(joint.columns) or covariance.n_observations != len(joint):
        raise ValueError("Covariance estimator changed the supplied assets or observations.")
    return RelativeRiskResult(
        assets=list(asset_returns.columns),
        covariance_weekly=covariance.covariance_weekly,
        factor_weekly=psd_factor(covariance.covariance_weekly.to_numpy()),
        shrinkage=covariance.shrinkage,
        n_observations=covariance.n_observations,
        observation_start=str(joint.index[0].date()),
        observation_end=str(joint.index[-1].date()),
    )


def tracking_error_weekly(risk: RelativeRiskResult, weights: pd.Series) -> float:
    """Model standard deviation of asset portfolio return minus full WLS return."""
    if weights.index.has_duplicates or set(weights.index) != set(risk.assets):
        raise ValueError("Weights must identify exactly the risk assets.")
    values = weights.reindex(risk.assets).to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Weights must be finite.")
    labels = [*risk.assets, BENCHMARK]
    if (
        list(risk.covariance_weekly.index) != labels
        or list(risk.covariance_weekly.columns) != labels
    ):
        raise ValueError("Joint covariance labels do not match risk assets.")
    factor = psd_factor(risk.covariance_weekly.to_numpy())
    return float(np.linalg.norm(factor @ np.r_[values, -1.0]))
