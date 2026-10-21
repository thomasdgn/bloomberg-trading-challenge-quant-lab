"""Paired moving-block bootstrap of three buy-and-hold candidate portfolios.

This is a transparent stress exploration, NOT calibrated probabilities, expected
returns, an execution forecast, or an estimate of global competition ranking.
"""

from __future__ import annotations

import hashlib
import json
import random
from math import isfinite
from typing import Any

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.schema import CASH, prepare

ENGINE_VERSION = "gtc-digital-twin-v2-self-financing"


def fingerprint(document: Any) -> str:
    raw = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (index - low) * (ordered[high] - ordered[low])


def _turnover(existing: dict[str, float], target: dict[str, float]) -> float:
    # One-way traded wealth, both equity legs and cash included.
    return 0.5 * sum(abs(existing[k] - target[k]) for k in existing)


def _self_financing_cost(
    existing: dict[str, float],
    target: dict[str, float],
    cost_bps: float,
) -> tuple[float, float]:
    """Solve exact one-off proportional costs using POST-cost target weights.

    NAV after execution is 1 - fee; trading each dollar leg is based on this
    NAV, not initial pre-fee notionals. This allows fully invested portfolios
    to self-finance costs without phantom negative cash or >100% holdings.
    """
    rate = cost_bps / 10_000
    nominal = _turnover(existing, target)
    if rate == 0 or nominal == 0:
        return 0.0, nominal

    def actual_turnover(fee: float) -> float:
        remaining = 1.0 - fee
        return 0.5 * sum(abs(remaining * target[name] - existing[name]) for name in existing)

    lower, upper = 0.0, rate
    for _ in range(64):
        middle = (lower + upper) / 2
        if middle < rate * actual_turnover(middle):
            lower = middle
        else:
            upper = middle
    fee = (lower + upper) / 2
    return fee, actual_turnover(fee)


def _path(
    returns: list[dict[str, Any]],
    indices: list[int],
    weights: dict[str, float],
    upfront_cost_fraction: float,
) -> dict[str, float]:
    # Dollar holdings preserve post-fee target weights at NAV=1-fee.
    values = {name: weight * (1.0 - upfront_cost_fraction) for name, weight in weights.items()}
    benchmark = 1.0
    # Include any immediate execution-cost drawdown against pre-trade wealth 1.
    relative_peak = 1.0
    max_drawdown = -upfront_cost_fraction
    for loc in indices:
        observation = returns[loc]
        benchmark *= 1.0 + observation["wls"]
        for name in values:
            if name != CASH:
                values[name] *= 1.0 + observation["returns"][name]
        ratio = sum(values.values()) / benchmark
        relative_peak = max(relative_peak, ratio)
        max_drawdown = min(max_drawdown, ratio / relative_peak - 1.0)
    wealth = sum(values.values())
    if not isfinite(wealth) or not isfinite(benchmark) or benchmark <= 0:
        raise DataBlocked("simulation produced non-finite/invalid wealth")
    return {
        "portfolio_return": wealth - 1,
        "wls_return": benchmark - 1,
        "relative_wealth": wealth / benchmark - 1,
        "active_return_points": wealth - benchmark,
        "max_relative_drawdown": max_drawdown,
    }


def simulate(payload: dict[str, Any]) -> dict[str, Any]:
    inputs = prepare(payload)
    paths = inputs["paths"]
    block = inputs["block"]
    length = inputs["horizon_sessions"]
    history = inputs["history"]
    rng = random.Random(inputs["seed"])
    weights = inputs["scenarios"]
    start = inputs["holdings"]
    costs = inputs["cost_bps"]
    scenario_details = {}
    for label, target in weights.items():
        fee, turnover = _self_financing_cost(start, target, costs)
        scenario_details[label] = {
            "weights": target,
            "one_way_turnover": turnover,
            "indicative_pre_fee_turnover": _turnover(start, target),
            "assumed_execution_cost_bps": costs,
            "one_off_cost_fraction_of_nav": fee,
            "post_cost_nav_fraction": 1.0 - fee,
            "equity_weight": sum(value for k, value in target.items() if k != CASH),
            "cash_weight": target[CASH],
        }
    sampled = {name: [] for name in weights}
    improvement = {name: [] for name in weights if name != "HOLD"}
    for _ in range(paths):
        # Same contiguous block draws across all three scenarios preserve paired
        # market paths, co-movement and lag structure inside each 5-session block.
        sequence = []
        while len(sequence) < length:
            start_at = rng.randrange(len(history) - block + 1)
            sequence.extend(range(start_at, start_at + block))
        sequence = sequence[:length]
        trial = {
            name: _path(
                history,
                sequence,
                target,
                scenario_details[name]["one_off_cost_fraction_of_nav"],
            )
            for name, target in weights.items()
        }
        for name in weights:
            sampled[name].append(trial[name])
            if name != "HOLD":
                improvement[name].append(
                    trial[name]["relative_wealth"] - trial["HOLD"]["relative_wealth"]
                )
    summaries = {}
    for name, observations in sampled.items():
        rel = [x["relative_wealth"] for x in observations]
        draw = [x["max_relative_drawdown"] for x in observations]
        res = {
            **scenario_details[name],
            "relative_wealth_p10": _percentile(rel, 0.10),
            "relative_wealth_median": _percentile(rel, 0.50),
            "relative_wealth_p90": _percentile(rel, 0.90),
            "empirical_fraction_beating_wls": sum(x > 0 for x in rel) / paths,
            "relative_drawdown_p10": _percentile(draw, 0.10),
            "relative_drawdown_median": _percentile(draw, 0.50),
            "mean_relative_wealth": sum(rel) / paths,
        }
        if name != "HOLD":
            paired = improvement[name]
            res["paired_improvement_over_hold_median"] = _percentile(paired, 0.50)
            res["paired_improvement_over_hold_p10"] = _percentile(paired, 0.10)
            res["fraction_simulations_improving_hold"] = sum(x > 0 for x in paired) / paths
        summaries[name] = res
    return {
        "status": "SIMULATION_ONLY",
        "execution_authorized": False,
        "input_sha256": fingerprint(payload),
        "run_id": fingerprint(
            {
                "inputs": fingerprint(payload),
                "implementation": ENGINE_VERSION,
            }
        )[:20],
        "method": {
            "engine_version": ENGINE_VERSION,
            "name": "paired moving-block bootstrap",
            "historical_panel": "joint daily price-only USD returns for current candidate set",
            "paths": paths,
            "seed": inputs["seed"],
            "block_size_sessions": block,
            "observed_history_rows": len(history),
            "history_start": history[0]["date"],
            "history_end": history[-1]["date"],
            "horizon_sessions": length,
            "decision_date": inputs["as_of_date"],
            "competition_end": inputs["challenge_end"],
            "source": inputs["source"],
            "execution_cost_model": (
                "self-financing: fee = bps * actual one-way turnover;"
                " weights reference post-fee NAV"
            ),
        },
        "summaries": summaries,
        "disclosures": [
            "Fractions are frequencies under historical bootstrap, NOT calibrated probabilities.",
            "This simulation DOES NOT estimate the probability of finishing top 1 globally.",
            "All three scenarios share paired bootstrap paths; assets drift without rebalancing.",
            "Current-universe selection introduces survivorship bias; not a backtest.",
            "USD cash does not track WLS; less equity can lose in rising markets.",
            "No validated Elastic Net alpha forecast or execution fill likelihood is injected.",
            "No dividends, corporate actions, impact, taxes or unmodeled FX slippage.",
            "Inspect official TMSG P&L, liquidity and eligibility before any human decision.",
        ],
    }
