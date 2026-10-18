"""Risk attribution and hypothetical reweighting; never an order generator."""

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def attribution(weights, benchmark, covariance, metadata):
    """Euler decomposition of annual TE, including every benchmark underweight."""
    active = weights - benchmark
    annual = covariance * 52
    product = annual @ active
    variance = float(active @ product)
    if variance < -1e-10:
        raise ValueError("Negative active variance.")
    te = float(np.sqrt(max(0, variance)))
    marginal = product / te if te > 1e-14 else product * 0
    table = metadata.reindex(weights.index).copy()
    table["portfolio_weight"] = weights
    table["benchmark_weight"] = benchmark
    table["active_weight"] = active
    table["marginal_te"] = marginal
    table["total_te_contribution"] = active * marginal
    table["share_of_te"] = table.total_te_contribution / te if te > 1e-14 else 0
    table.index.name = "id"
    groups = {
        field: table.groupby(field, dropna=False)["total_te_contribution"].sum()
        for field in ("sector", "country", "currency")
    }
    if not np.isclose(table.total_te_contribution.sum(), te, atol=1e-10):
        raise ValueError("Euler contributions do not reconcile.")
    top = table.sort_values("total_te_contribution", ascending=False).head(15)
    return te, table, groups, top


def rule_violations(weights, metadata, rules=None, *, baseline=None):
    """Unknown regulation clauses are rejected, never assumed satisfied."""
    allowed = {
        "source",
        "long_only",
        "max_weight",
        "min_cash_weight",
        "max_cash_weight",
        "max_gross_weight",
        "max_one_way_turnover",
        "sector_caps",
        "country_caps",
        "currency_caps",
    }
    if rules is not None and set(rules) - allowed:
        raise ValueError(f"Unsupported regulation clauses: {sorted(set(rules) - allowed)}")
    if rules is not None and not rules.get("source"):
        raise ValueError("Regulation requires a source reference.")
    spec = rules or {}
    for name in (
        "max_weight",
        "min_cash_weight",
        "max_cash_weight",
        "max_gross_weight",
        "max_one_way_turnover",
    ):
        if name in spec and (not np.isfinite(spec[name]) or spec[name] < 0):
            raise ValueError(f"Invalid regulation value: {name}.")
    if "long_only" in spec and not isinstance(spec["long_only"], bool):
        raise ValueError("long_only must be a boolean.")
    issues = []
    if not np.isfinite(weights).all() or not np.isclose(weights.sum(), 1, atol=1e-8):
        issues.append("invalid_total_weight")
    if spec.get("long_only", True) and weights.min() < -1e-8:
        issues.append("negative_weight")
    cash = weights.index.str.startswith("CASH:")
    if float(weights[~cash].max()) > float(spec.get("max_weight", 1)) + 1e-8:
        issues.append("max_weight")
    cash_weight = float(weights[cash].sum())
    if cash_weight < float(spec.get("min_cash_weight", 0)) - 1e-8:
        issues.append("min_cash_weight")
    if cash_weight > float(spec.get("max_cash_weight", 1)) + 1e-8:
        issues.append("max_cash_weight")
    if weights.abs().sum() > float(spec.get("max_gross_weight", 1)) + 1e-8:
        issues.append("max_gross_weight")
    if "max_one_way_turnover" in spec:
        if baseline is None:
            raise ValueError("Turnover constraint requires baseline weights.")
        if float((weights - baseline).abs().sum() / 2) > spec["max_one_way_turnover"] + 1e-8:
            issues.append("max_one_way_turnover")
    for field in ("sector", "country", "currency"):
        caps = spec.get(f"{field}_caps", {})
        grouped = weights.groupby(metadata[field]).sum()
        for group, cap in caps.items():
            if not np.isfinite(cap) or not 0 <= cap <= 1:
                raise ValueError(f"Invalid {field} cap.")
            if grouped.get(group, 0) > cap + 1e-8:
                issues.append(f"{field}:{group}")
    return issues


def homogeneous(weights, benchmark, covariance, metadata, rules=None):
    baseline_te = attribution(weights, benchmark, covariance, metadata)[0]
    rows = []
    for factor in (0.5, 0.75, 1.5):
        simulated = benchmark + factor * (weights - benchmark)
        te = attribution(simulated, benchmark, covariance, metadata)[0]
        if not np.isclose(te, factor * baseline_te, atol=1e-10):
            raise ValueError("Homogeneity check failed.")
        issues = rule_violations(simulated, metadata, rules, baseline=weights)
        rows.append(
            {
                "active_weight_factor": factor,
                "annual_te_theoretical": te,
                "basic_feasible": not issues,
                "violations": issues,
                "challenge_constraints": "checked_supplied_rules_only" if rules else "not_supplied",
            }
        )
    return rows


def targeted(weights, benchmark, covariance, metadata, *, max_subsets=5000, rules=None):
    """Sell long equity lines into USD cash; exhaustive increasing cardinality.

    A convex tangent lower bound certifies rejected box subproblems, to tolerance.
    Solver failure or a search limit never becomes a claim of minimum cardinality.
    """
    if max_subsets < 1:
        raise ValueError("max_subsets must be positive.")
    violations = rule_violations(weights, metadata, rules, baseline=weights)
    if violations:
        return {"status": "blocked_initial_constraints", "violations": violations, "reductions": []}
    active = (weights - benchmark).to_numpy()
    sigma = covariance.to_numpy() * 52
    initial = float(active @ sigma @ active)
    if initial < 1e-20:
        return {"status": "already_zero", "transactions": 0, "reductions": []}
    threshold = initial / 4
    tolerance = max(1e-12, initial * 1e-8)
    ids = [i for i in weights.index if not i.startswith("CASH:") and weights[i] > 1e-10]
    if not ids:
        return {"status": "infeasible_sales_only", "reductions": []}
    cash = weights.index.get_loc("CASH:USD")
    positions = [weights.index.get_loc(i) for i in ids]
    direction = np.zeros((len(weights), len(ids)))
    direction[positions, np.arange(len(ids))] = -1
    direction[cash, :] = 1
    q = direction.T @ sigma @ direction
    g = direction.T @ sigma @ active
    upper = weights.loc[ids].to_numpy()

    def solve(chosen):
        chosen = list(chosen)
        qs = q[np.ix_(chosen, chosen)]
        gs, ub = g[chosen], upper[chosen]

        def value(x):
            return float(initial + 2 * gs @ x + x @ qs @ x)

        def gradient(x):
            return 2 * (gs + qs @ x)

        result = minimize(
            value,
            ub / 2,
            jac=gradient,
            method="SLSQP",
            bounds=list(zip(np.zeros(len(chosen)), ub, strict=True)),
            options={"ftol": 1e-13, "maxiter": 1000},
        )
        x = np.clip(result.x, 0, ub)
        grad = gradient(x)
        lower = value(x) + np.where(grad >= 0, grad * -x, grad * (ub - x)).sum()
        return chosen, x, value(x), float(lower)

    # A lower bound from the unrestricted sales box can prove global infeasibility.
    _, _, _, lower_all = solve(range(len(ids)))
    if lower_all > threshold + tolerance:
        return {
            "status": "infeasible_sales_only",
            "reductions": [],
            "minimum_te_lower_bound": float(np.sqrt(max(0, lower_all))),
        }
    checked, unresolved = 0, False
    for count in range(1, len(ids) + 1):
        for subset in combinations(range(len(ids)), count):
            if checked >= max_subsets:
                return {
                    "status": "search_limit_minimum_not_proven",
                    "subsets": checked,
                    "reductions": [],
                }
            chosen, x, variance, lower = solve(subset)
            checked += 1
            if not np.isfinite(variance) or not np.isfinite(lower):
                unresolved = True
                continue
            if variance <= threshold + tolerance:
                full = np.zeros(len(ids))
                full[chosen] = x
                simulated = pd.Series(weights.to_numpy() + direction @ full, index=weights.index)
                if rule_violations(simulated, metadata, rules, baseline=weights):
                    # Constraints can require another amount on this same subset.
                    # Do not pretend the unconstrained minimum rules out feasibility.
                    unresolved = True
                    continue
                reductions = [
                    {"id": ids[j], "weight_reduction": float(full[j])}
                    for j in range(len(ids))
                    if full[j] > 1e-10
                ]
                te = attribution(simulated, benchmark, covariance, metadata)[0]
                if te > np.sqrt(initial) / 2 + np.sqrt(tolerance):
                    raise ValueError("Targeted result fails independent risk check.")
                return {
                    "status": "minimum_proven_to_tolerance"
                    if not unresolved
                    else "feasible_minimum_not_proven",
                    "annual_te": te,
                    "transactions": len(reductions),
                    "subsets": checked,
                    "variance_tolerance": tolerance,
                    "cash_proceeds_weight": float(full.sum()),
                    "reductions": reductions,
                    "challenge_constraints": "checked_supplied_rules_only"
                    if rules
                    else "not_supplied",
                }
            if lower <= threshold + tolerance:
                unresolved = True
    return {
        "status": "unresolved_numerically" if unresolved else "infeasible_sales_only",
        "subsets": checked,
        "reductions": [],
    }
