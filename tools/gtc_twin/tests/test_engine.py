"""Safety, reproducibility and paired scenario regression tests."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.engine import simulate


def test_three_scenarios_are_computed_and_seed_is_deterministic(example_payload) -> None:
    first = simulate(example_payload)
    second = simulate(deepcopy(example_payload))
    assert first == second
    assert first["status"] == "SIMULATION_ONLY"
    assert first["execution_authorized"] is False
    assert set(first["summaries"]) == {"HOLD", "REBALANCE", "DEFENSIVE"}
    assert first["summaries"]["HOLD"]["one_way_turnover"] == 0
    assert first["summaries"]["REBALANCE"]["one_way_turnover"] == pytest.approx(0.1)
    assert first["summaries"]["DEFENSIVE"]["cash_weight"] == pytest.approx(0.8)
    assert first["method"]["horizon_sessions"] > 0
    assert first["run_id"]


def test_same_weights_as_hold_produce_identical_paired_paths(example_payload) -> None:
    source = deepcopy(example_payload)
    source["rebalance_weights"] = {
        "SYNTH_A UN Equity": 0.2,
        "SYNTH_B UN Equity": 0.2,
        "USD_CASH": 0.6,
    }
    result = simulate(source)
    assert result["summaries"]["REBALANCE"]["one_way_turnover"] == 0
    assert result["summaries"]["REBALANCE"]["paired_improvement_over_hold_median"] == 0
    assert result["summaries"]["REBALANCE"]["fraction_simulations_improving_hold"] == 0


def test_execution_costs_do_not_apply_to_unchanged_hold(example_payload) -> None:
    expensive = deepcopy(example_payload)
    expensive["assumed_execution_cost_bps"] = 200
    result = simulate(expensive)
    assert result["summaries"]["HOLD"]["one_off_cost_fraction_of_nav"] == 0
    assert result["summaries"]["REBALANCE"]["one_off_cost_fraction_of_nav"] == pytest.approx(
        0.002
    )


@pytest.mark.parametrize("violation", [
    lambda p: p["rebalance_weights"].update({"SYNTH_A UN Equity": 0.40}),
    lambda p: p["rebalance_weights"].update({"ETF NOT WLS": 0.05}),
    lambda p: p["snapshot"]["pending_orders"].append({
        "order_id": "unfilled", "status": "OPEN", "id": "SYNTH_A UN Equity",
        "side": "BUY", "remaining_quantity": 1, "limit_price_local": 100,
    }),
    lambda p: p["history"][-1].update(date="2026-10-21"),
    lambda p: p["history"][-1]["returns"].pop("SYNTH_A UN Equity"),
    lambda p: p["history"][-1].update(wls=float("nan")),
    lambda p: p["data_verification"].update(basis="LOCAL_CURRENCY"),
    lambda p: p["data_verification"].update(benchmark_id="SPY"),
    lambda p: p["data_verification"].update(verified_by_operator=False),
    lambda p: p.update(bootstrap_paths=20),
    lambda p: p.update(defensive_equity_scale=1.1),
    lambda p: p.update(decision_cutoff="2026-10-20"),
    lambda p: p["verified_exchange_sessions"].pop(),
])
def test_unsafe_or_lookahead_inputs_are_rejected(example_payload, violation) -> None:
    input_data = deepcopy(example_payload)
    violation(input_data)
    with pytest.raises(DataBlocked):
        simulate(input_data)


def test_forecast_does_not_claim_statistical_probability(example_payload) -> None:
    result = simulate(example_payload)
    assert all("NOT calibrated" in statement or "probability" in statement
               for statement in result["disclosures"][:2])
    for row in result["summaries"].values():
        assert 0 <= row["empirical_fraction_beating_wls"] <= 1
        assert row["relative_wealth_p10"] <= row["relative_wealth_median"]
        assert row["relative_wealth_median"] <= row["relative_wealth_p90"]
