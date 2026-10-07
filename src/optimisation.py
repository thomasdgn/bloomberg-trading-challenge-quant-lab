"""Fully invested, long-only minimum tracking-error reference (no alpha)."""

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
import pandas as pd

from src.risk_relative import BENCHMARK, RelativeRiskResult, psd_factor, tracking_error_weekly


class AllocationError(ValueError):
    """No independently verified feasible reference allocation is available."""


@dataclass(frozen=True)
class ReferenceAllocation:
    weights: pd.Series
    tracking_error_weekly: float
    tracking_error_annualized_approx: float
    solver_status: str
    solver: str
    max_constraint_violation: float
    exposure_values: dict[str, float]


def minimum_tracking_error(
    risk: RelativeRiskResult,
    *,
    max_weight: float | pd.Series = 0.18,
    exposures: pd.DataFrame | None = None,
    exposure_bounds: dict[str, tuple[float, float]] | None = None,
    max_tracking_error_weekly: float | None = None,
) -> ReferenceAllocation:
    """Solve minimum TE under caps and optional absolute exposure bounds.

    Bounds are explicit team inputs, never inferred from partial index weights.
    No clipping/renormalization of solver weights, no optimal_inaccurate fallback.
    Annualized TE uses sqrt(52), an approximation rather than a forecast.
    """
    assets = risk.assets
    if not assets or len(set(assets)) != len(assets):
        raise ValueError("Risk asset identifiers must be unique and nonempty.")
    labels = [*assets, BENCHMARK]
    cov = risk.covariance_weekly
    if list(cov.index) != labels or list(cov.columns) != labels:
        raise ValueError("Joint covariance labels do not match risk assets.")
    factor = psd_factor(cov.to_numpy())
    if isinstance(max_weight, pd.Series):
        if max_weight.index.has_duplicates or set(max_weight.index) != set(assets):
            raise ValueError("Weight caps must identify exactly the risk assets.")
        caps = max_weight.reindex(assets).to_numpy(dtype=float)
    else:
        caps = np.full(len(assets), float(max_weight))
    if not np.isfinite(caps).all() or (caps <= 0).any() or (caps > 1).any():
        raise ValueError("Weight caps must be finite fractions in (0, 1].")
    if caps.sum() < 1 - 1e-12:
        raise AllocationError("Infeasible: weight caps cannot fund a fully invested portfolio.")
    if max_tracking_error_weekly is not None and (
        not np.isfinite(max_tracking_error_weekly) or max_tracking_error_weekly < 0
    ):
        raise ValueError("TE ceiling must be a finite nonnegative weekly fraction.")
    bounds = exposure_bounds or {}
    if (exposures is None) != (not bounds):
        raise ValueError("Supply exposures and their bounds together.")
    if exposures is not None:
        if (
            exposures.index.has_duplicates
            or set(exposures.index) != set(assets)
            or exposures.columns.has_duplicates
            or set(exposures.columns) != set(bounds)
        ):
            raise ValueError("Exposures must cover exactly the assets and bounded columns.")
        exposures = exposures.reindex(assets).astype(float)
        if not np.isfinite(exposures.to_numpy()).all():
            raise ValueError("Exposure coefficients must be finite.")
    w = cp.Variable(len(assets))
    constraints = [cp.sum(w) == 1, w >= 0, w <= caps]
    for name, (lower, upper) in bounds.items():
        if not np.isfinite([lower, upper]).all() or lower > upper:
            raise ValueError(f"Invalid bounds for {name}.")
        value = exposures[name].to_numpy() @ w
        constraints.extend([value >= lower, value <= upper])
    # Dividing the factor by its scale improves conditioning without changing
    # the minimizer; avoid losing a small weekly variance in solver tolerances.
    scale = max(float(np.linalg.norm(factor, axis=1).max()), 1e-12)
    problem = cp.Problem(
        cp.Minimize(cp.sum_squares((factor / scale) @ cp.hstack([w, -1]))), constraints
    )
    try:
        problem.solve(solver=cp.CLARABEL, tol_gap_abs=1e-10, tol_gap_rel=1e-10, tol_feas=1e-10)
    except cp.error.SolverError as exc:
        raise AllocationError(f"CLARABEL failed: {exc}") from exc
    if problem.status != cp.OPTIMAL or w.value is None:
        raise AllocationError(f"No verified optimum: solver status {problem.status}.")
    values = np.asarray(w.value, dtype=float)
    if not np.isfinite(values).all():
        raise AllocationError("Solver returned nonfinite weights.")
    violations = [
        abs(values.sum() - 1),
        float(max(0, -values.min())),
        float(max(0, (values - caps).max())),
    ]
    exposure_values = {}
    for name, (lower, upper) in bounds.items():
        value = float(exposures[name].to_numpy() @ values)
        exposure_values[name] = value
        violations.extend([max(0, lower - value), max(0, value - upper)])
    violation = max(violations)
    if violation > 1e-8:
        raise AllocationError(f"Independent constraint check failed: {violation:.3g}.")
    weights = pd.Series(values, index=assets, name="weight")
    te = tracking_error_weekly(risk, weights)
    if max_tracking_error_weekly is not None and te > max_tracking_error_weekly + 1e-10:
        raise AllocationError(
            f"Minimum feasible weekly TE {te:.8g} exceeds ceiling {max_tracking_error_weekly:.8g}."
        )
    return ReferenceAllocation(
        weights=weights,
        tracking_error_weekly=te,
        tracking_error_annualized_approx=te * np.sqrt(52),
        solver_status=str(problem.status),
        solver="CLARABEL",
        max_constraint_violation=violation,
        exposure_values=exposure_values,
    )
