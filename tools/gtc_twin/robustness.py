"""Sensitivity grid: test whether scenario rankings survive plausible modelling choices.

A scenario that looks attractive only at one cost estimate or one bootstrap block
length is fragile. This is not a fitted probability or a market timing forecast.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.engine import fingerprint, simulate
from tools.gtc_twin.schema import prepare

LABELS = ("HOLD", "REBALANCE", "DEFENSIVE")


def sensitivity_grid(
    payload: dict[str, Any],
    *,
    cost_bps: list[float] | None = None,
    block_sizes: list[int] | None = None,
) -> dict[str, Any]:
    baseline = prepare(payload)
    center = baseline["cost_bps"]
    if cost_bps is None:
        prices = (
            [0.0, 10.0, 25.0] if center == 0
            else [50.0, 150.0, 300.0] if center == 300
            else [center / 2, center, min(300.0, center * 2)]
        )
    else:
        prices = cost_bps
    original_block = baseline["block"]
    if block_sizes is None:
        blocks = (
            [1, 2, 5] if original_block == 1
            else [5, 10, 20] if original_block == 20
            else [max(1, original_block // 2),
                  original_block, min(20, original_block * 2)]
        )
    else:
        blocks = block_sizes
    if not isinstance(prices, list) or not isinstance(blocks, list):
        raise DataBlocked("sensitivity grids must be explicit lists")
    if len(prices) < 2 or len(blocks) < 2 or len(prices) * len(blocks) > 16:
        raise DataBlocked("grid requires 2+ distinct choices and at most 16 cells")
    if (
        any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in prices)
        or any(isinstance(x, bool) or not isinstance(x, int) for x in blocks)
    ):
        raise DataBlocked("grid requires numeric costs and integer blocks")
    if (
        len(set(prices)) != len(prices) or len(set(blocks)) != len(blocks)
        or any(x < 0 or x > 300 for x in prices)
        or any(x < 1 or x > 20 for x in blocks)
    ):
        raise DataBlocked("duplicate or out-of-range grid values")
    if any(block > len(baseline["history"]) for block in blocks):
        raise DataBlocked("grid block exceeds observed market history")

    cells = []
    winner_counts = {key: 0 for key in LABELS}
    for block in sorted(blocks):
        for cost in sorted(prices):
            data = deepcopy(payload)
            data["assumed_execution_cost_bps"] = float(cost)
            data["block_size_sessions"] = block
            report = simulate(data)
            medians = {
                key: report["summaries"][key]["relative_wealth_median"]
                for key in LABELS
            }
            maximum = max(medians.values())
            # Do not arbitrarily break ties and report a spurious "winner".
            winners = [key for key in LABELS if abs(medians[key] - maximum) <= 1e-12]
            if len(winners) == 1:
                winner_counts[winners[0]] += 1
            cells.append({
                "execution_cost_bps": float(cost),
                "block_size_sessions": block,
                "run_id": report["run_id"],
                "median_relative_wealth": medians,
                "unique_median_winner": winners[0] if len(winners) == 1 else None,
                "paired_vs_hold": {
                    key: report["summaries"][key]["paired_improvement_over_hold_median"]
                    for key in LABELS if key != "HOLD"
                },
            })
    return {
        "status": "SENSITIVITY_ONLY", "execution_authorized": False,
        "original_input_sha256": fingerprint(payload),
        "total_cells": len(cells), "unique_winner_counts": winner_counts,
        "cells": cells,
        "interpretation": (
            "Winner counts are not probabilistic evidence: grid cells reuse the same "
            "historical sample and seed. A fragile ranking warrants more validation."
        ),
    }
