"""Sensitivity guardrails for transparent scenario comparison."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.robustness import sensitivity_grid


def test_sensitivity_grid_reproducible_and_explicit(example_payload) -> None:
    a = sensitivity_grid(example_payload, cost_bps=[0.0, 25.0], block_sizes=[3, 7])
    b = sensitivity_grid(deepcopy(example_payload), cost_bps=[0.0, 25.0], block_sizes=[3, 7])
    assert a == b
    assert a["status"] == "SENSITIVITY_ONLY"
    assert a["execution_authorized"] is False
    assert a["total_cells"] == 4
    assert sum(a["unique_winner_counts"].values()) <= a["total_cells"]
    assert all(
        row["unique_median_winner"] in {None, "HOLD", "REBALANCE", "DEFENSIVE"}
        for row in a["cells"]
    )


def test_same_cost_only_block_change_not_a_new_probability(example_payload) -> None:
    report = sensitivity_grid(example_payload, cost_bps=[0.0, 15.0], block_sizes=[1, 5])
    assert "not probabilistic" in report["interpretation"]
    assert set(report["cells"][0]["median_relative_wealth"]) == {
        "HOLD",
        "REBALANCE",
        "DEFENSIVE",
    }


@pytest.mark.parametrize(
    "costs,blocks",
    [
        ([1.0], [3, 5]),
        ([1.0, 1.0], [3, 5]),
        ([1.0, 5.0], [5, 5]),
        ([-1.0, 5.0], [3, 5]),
        ([0, 400], [3, 5]),
        ([0, 20], [0, 5]),
        ([0, 20], [3, 21]),
        ([0, float("nan")], [3, 5]),
        ([0, 15], [True, 5]),
    ],
)
def test_bad_sensitivity_options_block(example_payload, costs, blocks) -> None:
    with pytest.raises(DataBlocked):
        sensitivity_grid(example_payload, cost_bps=costs, block_sizes=blocks)
