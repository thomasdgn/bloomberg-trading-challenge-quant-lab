"""Safety, reproducibility and paired scenario regression tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.engine import _path, _self_financing_cost, _turnover, simulate


def test_three_scenarios_are_computed_and_seed_is_deterministic(example_payload) -> None:
    first = simulate(example_payload)
    second = simulate(deepcopy(example_payload))
    assert first == second
    assert first["status"] == "SIMULATION_ONLY"
    assert first["execution_authorized"] is False
    assert set(first["summaries"]) == {"HOLD", "REBALANCE", "DEFENSIVE"}
    assert first["summaries"]["HOLD"]["one_way_turnover"] == 0
    rebalance = first["summaries"]["REBALANCE"]
    assert rebalance["indicative_pre_fee_turnover"] == pytest.approx(0.1)
    assert rebalance["one_off_cost_fraction_of_nav"] == pytest.approx(
        rebalance["one_way_turnover"] * 15.0 / 10_000
    )
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
    rebalance = result["summaries"]["REBALANCE"]
    assert rebalance["one_off_cost_fraction_of_nav"] == pytest.approx(
        rebalance["one_way_turnover"] * 200.0 / 10_000
    )


@pytest.mark.parametrize(
    "violation",
    [
        lambda p: p["rebalance_weights"].update({"SYNTH_A UN Equity": 0.40}),
        lambda p: p["rebalance_weights"].update({"ETF NOT WLS": 0.05}),
        lambda p: p["snapshot"]["pending_orders"].append(
            {
                "order_id": "unfilled",
                "status": "OPEN",
                "id": "SYNTH_A UN Equity",
                "side": "BUY",
                "remaining_quantity": 1,
                "limit_price_local": 100,
            }
        ),
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
    ],
)
def test_unsafe_or_lookahead_inputs_are_rejected(example_payload, violation) -> None:
    input_data = deepcopy(example_payload)
    violation(input_data)
    with pytest.raises(DataBlocked):
        simulate(input_data)


def test_forecast_does_not_claim_statistical_probability(example_payload) -> None:
    result = simulate(example_payload)
    assert all(
        "NOT calibrated" in statement or "probability" in statement
        for statement in result["disclosures"][:2]
    )
    for row in result["summaries"].values():
        assert 0 <= row["empirical_fraction_beating_wls"] <= 1
        assert row["relative_wealth_p10"] <= row["relative_wealth_median"]
        assert row["relative_wealth_median"] <= row["relative_wealth_p90"]


def test_exact_costs_are_self_financing_and_preserve_target_weights() -> None:
    initial = {"STOCK_A": 0.2, "STOCK_B": 0.2, "USD_CASH": 0.6}
    target = {"STOCK_A": 0.1, "STOCK_B": 0.2, "USD_CASH": 0.7}
    fee, turnover = _self_financing_cost(initial, target, 150.0)
    assert 0 < fee < 0.015
    assert fee == pytest.approx(0.015 * turnover)
    post_fee = {ticker: weight * (1 - fee) for ticker, weight in target.items()}
    assert sum(post_fee.values()) == pytest.approx(1 - fee)
    assert post_fee["STOCK_A"] / (1 - fee) == pytest.approx(target["STOCK_A"])
    assert post_fee["STOCK_B"] / (1 - fee) == pytest.approx(target["STOCK_B"])


def test_fully_invested_rotation_does_not_create_negative_cash() -> None:
    initial = {"STOCK_A": 0.5, "STOCK_B": 0.5, "USD_CASH": 0.0}
    target = {"STOCK_A": 0.25, "STOCK_B": 0.75, "USD_CASH": 0.0}
    fee, turnover = _self_financing_cost(initial, target, 50.0)
    assert fee == pytest.approx(0.005 * turnover)
    values = {name: weight * (1 - fee) for name, weight in target.items()}
    assert values["USD_CASH"] == 0
    assert sum(values.values()) == pytest.approx(1 - fee)


def test_drawdown_records_execution_cost_even_with_flat_market() -> None:
    positions = {"STOCK_A": 0.2, "USD_CASH": 0.8}
    out = _path(
        [{"wls": 0.0, "returns": {"STOCK_A": 0.0}}],
        [0],
        positions,
        0.002,
    )
    assert out["portfolio_return"] == pytest.approx(-0.002)
    assert out["relative_wealth"] == pytest.approx(-0.002)
    assert out["max_relative_drawdown"] == pytest.approx(-0.002)


def test_zero_cost_matches_no_trade_nominal_turnover() -> None:
    old = {"STOCK_A": 0.2, "USD_CASH": 0.8}
    target = {"STOCK_A": 0.3, "USD_CASH": 0.7}
    fee, actual = _self_financing_cost(old, target, 0)
    assert fee == 0
    assert actual == pytest.approx(_turnover(old, target))


def test_competition_default_has_no_assumed_execution_fees(example_payload) -> None:
    no_field = deepcopy(example_payload)
    no_field.pop("assumed_execution_cost_bps")
    zero_explicit = deepcopy(example_payload)
    zero_explicit["assumed_execution_cost_bps"] = 0.0

    default_result = simulate(no_field)
    explicit_result = simulate(zero_explicit)
    for label in ("HOLD", "REBALANCE", "DEFENSIVE"):
        a = default_result["summaries"][label]
        b = explicit_result["summaries"][label]
        assert a["assumed_execution_cost_bps"] == 0.0
        assert a["one_off_cost_fraction_of_nav"] == 0.0
        assert a["post_cost_nav_fraction"] == 1.0
        assert a["relative_wealth_median"] == pytest.approx(b["relative_wealth_median"])
    assert default_result["execution_authorized"] is False


def test_hypothetical_fees_only_reduce_wealth_in_flat_market(example_payload) -> None:
    none = deepcopy(example_payload)
    none["assumed_execution_cost_bps"] = 0.0
    friction = deepcopy(example_payload)
    friction["assumed_execution_cost_bps"] = 120.0
    for row in none["history"] + friction["history"]:
        row["wls"] = 0.0
        for ticker in row["returns"]:
            row["returns"][ticker] = 0.0
    baseline = simulate(none)["summaries"]
    stressed = simulate(friction)["summaries"]
    for label in ("HOLD", "REBALANCE", "DEFENSIVE"):
        assert baseline[label]["relative_wealth_median"] == pytest.approx(0.0)
    assert stressed["HOLD"]["relative_wealth_median"] == pytest.approx(0.0)
    assert stressed["REBALANCE"]["relative_wealth_median"] < 0
    assert stressed["DEFENSIVE"]["relative_wealth_median"] < 0
