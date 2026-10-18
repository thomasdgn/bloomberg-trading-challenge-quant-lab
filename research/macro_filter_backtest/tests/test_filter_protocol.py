"""Synthetic checks only: no real filtered result before the tag."""

import json

import numpy as np
import pandas as pd
import pytest

from research.macro_filter_backtest import config as cfg
from research.macro_filter_backtest.mechanics import (
    blend,
    filter_activation,
    information_ratio,
    k_series,
    rotation,
    series_metrics,
    switch_notional,
)
from research.macro_filter_backtest.statistics import (
    active_runs,
    conclusion,
    criterion,
    paired_difference,
    percentile_position,
    placebo_activation,
    placebo_medians,
)
from src.trading_config import ExecutionConfig
from src.transaction_costs import calculate_turnover


def audited_profile() -> ExecutionConfig:
    profiles = json.loads((cfg.SNAPSHOT / "config/execution_profiles.json").read_text())
    return ExecutionConfig(**profiles[cfg.PROFILE])


def test_blend_is_k_weighted_mix_with_k_one_outside_filters():
    portfolio = np.array([0.10, -0.05, 0.02, 0.04])
    benchmark = np.array([0.03, 0.01, -0.02, 0.00])
    k = k_series(np.array([False, True, True, False]))
    assert k.tolist() == [1.0, 0.5, 0.5, 1.0]
    returns, cost = blend(portfolio, benchmark, k, cost_bps=0.0)
    np.testing.assert_allclose(returns, [0.10, -0.02, 0.0, 0.04])
    assert cost.sum() == 0.0
    unfiltered, unfiltered_cost = blend(portfolio, benchmark, np.ones(4))
    np.testing.assert_array_equal(unfiltered, portfolio)
    assert unfiltered_cost.sum() == 0.0


def test_switch_cost_charges_each_change_of_k_at_existing_bps():
    k = np.array([1.0, 0.5, 0.5, 1.0, 0.5])
    notional = switch_notional(k)
    np.testing.assert_allclose(notional, [0.0, 1.0, 0.0, 1.0, 1.0])
    _, cost = blend(np.zeros(5), np.zeros(5), k, cost_bps=15.0)
    np.testing.assert_allclose(cost, notional * 15.0 / 10_000)
    # Permanent control: one initial switch from the unfiltered base, then none.
    np.testing.assert_allclose(switch_notional(np.full(3, 0.5)), [1.0, 0.0, 0.0])


def test_switch_notional_matches_existing_turnover_function_and_bps():
    profile = audited_profile()
    assert profile.total_cost_bps == cfg.COST_BPS
    for previous, current in [(1.0, 0.5), (0.5, 1.0), (0.5, 0.5), (1.0, 1.0)]:
        result = calculate_turnover(
            {"portfolio": previous, "wls": 1 - previous},
            {"portfolio": current, "wls": 1 - current},
            profile,
        )
        ours = switch_notional(np.array([current]), k_initial=previous)[0]
        assert result.traded_notional == pytest.approx(ours)
        assert result.transaction_cost_return == pytest.approx(ours * cfg.COST_BPS / 10_000)
        assert result.one_way_turnover == pytest.approx(ours / 2)


def test_rotation_scales_portfolio_turnover_and_adds_sleeve_switch():
    np.testing.assert_allclose(
        rotation(np.array([0.8, 0.8, 0.8]), np.array([1.0, 0.5, 1.0])), [0.8, 0.9, 1.3]
    )


def test_missing_component_leaves_filter_inactive_and_is_counted():
    frame = pd.DataFrame(
        {
            "A": pd.array([True, False, pd.NA, True, False], dtype="boolean"),
            "B": pd.array([False, False, True, pd.NA, True], dtype="boolean"),
        }
    )
    active, missing = filter_activation(frame, ("A", "B"))
    assert active.tolist() == [True, False, False, False, True]
    assert missing == 2


def test_permanent_half_exposure_keeps_ir_without_costs_and_halves_active():
    rng = np.random.default_rng(1)
    portfolio, benchmark = rng.normal(0.02, 0.05, 60), rng.normal(0.01, 0.03, 60)
    base_active = portfolio - benchmark
    returns, _ = blend(portfolio, benchmark, np.full(60, 0.5), cost_bps=0.0)
    np.testing.assert_allclose(returns - benchmark, 0.5 * base_active)
    assert information_ratio(returns - benchmark) == pytest.approx(information_ratio(base_active))


def test_series_metrics_on_known_path():
    returns, benchmark = np.array([0.10, -0.10, 0.05]), np.array([0.0, 0.0, 0.0])
    metrics = series_metrics(returns, benchmark, np.ones(3), np.ones(3))
    assert metrics["net_return"] == pytest.approx(1.1 * 0.9 * 1.05 - 1)
    assert metrics["max_relative_drawdown"] == pytest.approx(-0.10)
    assert metrics["hit_rate"] == pytest.approx(2 / 3)
    assert metrics["filtered_periods"] == 0
    expected_ir = returns.mean() / returns.std(ddof=1) * np.sqrt(52 / 5)
    assert metrics["information_ratio"] == pytest.approx(expected_ir)


def test_placebo_preserves_count_and_run_lengths_with_fixed_seed():
    reference = np.zeros(61, dtype=bool)
    reference[[3, 4, 5, 20, 40, 41, 60]] = True
    rng = np.random.default_rng(cfg.PLACEBO_SEED)
    draws = [placebo_activation(reference, rng) for _ in range(500)]
    for draw in draws:
        assert draw.sum() == reference.sum()
        assert sorted(active_runs(draw)) == sorted(active_runs(reference))
    assert len({draw.tobytes() for draw in draws}) > 400
    first = placebo_activation(reference, np.random.default_rng(7))
    second = placebo_activation(reference, np.random.default_rng(7))
    np.testing.assert_array_equal(first, second)
    positions = np.mean(draws, axis=0)
    assert positions.min() > 0.0  # every period can be activated


def test_placebo_handles_empty_and_full_activation():
    rng = np.random.default_rng(0)
    assert not placebo_activation(np.zeros(10, bool), rng).any()
    assert placebo_activation(np.ones(10, bool), rng).all()


def test_placebo_medians_are_deterministic_and_frequency_matched():
    rng = np.random.default_rng(3)
    per_offset = {o: (rng.normal(0.02, 0.05, 30), rng.normal(0.01, 0.03, 30)) for o in range(5)}
    activation = {o: np.arange(30) % (o + 4) == 0 for o in range(5)}
    first, counts = placebo_medians(per_offset, activation, seed=11, draws=50)
    second, _ = placebo_medians(per_offset, activation, seed=11, draws=50)
    np.testing.assert_array_equal(first, second)
    for offset, values in counts.items():
        assert set(values) == {int(activation[offset].sum())}


def test_paired_bootstrap_of_identical_series_is_zero():
    rng = np.random.default_rng(5)
    active = rng.normal(0.01, 0.04, 60)
    interval = paired_difference(active, active, seed=1, replicates=500)
    assert interval["delta_ir_ci_low"] == interval["delta_ir_ci_high"] == 0.0
    assert interval["delta_mean_active_ci_low"] == 0.0


def test_paired_bootstrap_detects_a_constant_shift():
    rng = np.random.default_rng(6)
    base = rng.normal(0.0, 0.04, 60)
    interval = paired_difference(base + 0.01, base, seed=2, replicates=500)
    expected = 0.01 * cfg.PERIODS_PER_YEAR
    assert interval["delta_mean_active_ci_low"] == pytest.approx(expected)
    assert interval["delta_mean_active_ci_high"] == pytest.approx(expected)


def test_criterion_requires_base_control_and_placebo():
    placebo = np.linspace(0.0, 1.0, 1001)
    passing = criterion({"base": 0.5, "T": 0.49, "F1": 0.96}, placebo)
    assert passing["met"] and passing["placebo_q95"] == pytest.approx(0.95)
    assert not criterion({"base": 0.97, "T": 0.49, "F1": 0.96}, placebo)["met"]
    assert not criterion({"base": 0.5, "T": 0.97, "F1": 0.96}, placebo)["met"]
    assert not criterion({"base": 0.5, "T": 0.49, "F1": 0.94}, placebo)["met"]
    assert percentile_position(0.5, placebo) == pytest.approx(50.0, abs=0.1)


def test_conclusion_wording_and_news_fragility():
    assert conclusion({"with_news": True, "without_news": True}).startswith("apport démontré")
    assert conclusion({"with_news": True, "without_news": False}).startswith("fragile")
    assert conclusion({"with_news": False, "without_news": True}) == "pas d'apport démontré"
    assert conclusion({"with_news": False, "without_news": False}) == "pas d'apport démontré"


def synthetic_inputs():
    rng = np.random.default_rng(9)
    weeks = pd.date_range("2021-01-01", periods=5 * 24, freq="W-FRI")
    base = pd.DataFrame(
        {
            "offset": np.arange(len(weeks)) % 5,
            "date": weeks,
            "end_date": weeks + pd.Timedelta(weeks=5),
            cfg.RETURN: rng.normal(0.02, 0.06, len(weeks)),
            cfg.BENCHMARK: rng.normal(0.01, 0.03, len(weeks)),
            "one_way_turnover": rng.uniform(0.5, 1.0, len(weeks)),
        }
    )
    days = pd.bdate_range(weeks.min() - pd.Timedelta(days=10), weeks.max())
    names = sorted({name for names in cfg.FILTERS.values() for name in names})
    frames = []
    for ablation in cfg.ABLATIONS:
        frame = pd.DataFrame({"date": days, "sample": "H", "mode": "strict", "ablation": ablation})
        frame["as_of_date"] = days.max()
        for number, name in enumerate(names):
            frame[name] = pd.array((np.arange(len(days)) // 17 + number) % 4 == 0, "boolean")
        frame.loc[frame.date.eq(weeks[7] - pd.Timedelta(days=1)), "CHOC_ENERGIE"] = pd.NA
        frames.append(frame)
    return base, pd.concat(frames, ignore_index=True)


def test_compute_pipeline_end_to_end_on_synthetic_data(monkeypatch):
    from research.macro_filter_backtest import compute

    monkeypatch.setattr(cfg, "PLACEBO_DRAWS", 40)
    base, labels = synthetic_inputs()
    series, missing = compute.build_series(base, labels)
    assert series.date.gt(series.macro_date).all()
    assert (series.macro_date == series.date - pd.Timedelta(days=1)).all()
    assert len(missing) == 2 * 1  # one unknown F3 label, counted in each ablation
    plain = series.loc[series.variant.eq("base")]
    np.testing.assert_allclose(plain["return"], plain.portfolio_return)
    control = series.loc[series.variant.eq("T")]
    assert control.k.eq(0.5).all()
    f3 = series.loc[series.variant.eq("F3") & series.date.eq(base.date[7])]
    assert not f3.filter_active.any() and f3.k.eq(1.0).all()
    metrics = compute.metrics_by_offset(series)
    assert len(metrics) == len(cfg.ABLATIONS) * len(cfg.VARIANTS) * len(cfg.OFFSETS)
    assert metrics.loc[metrics.variant.eq("F3"), "missing_label_periods"].sum() == 2
    by_year = compute.yearly(series)
    assert by_year.groupby(["ablation", "variant", "offset"]).periods.sum().eq(24).all()
    intervals = compute.bootstrap(series)
    assert len(intervals) == len(cfg.ABLATIONS) * 4 * len(cfg.OFFSETS)
    draws, summary, criteria, verdict = compute.placebo(series, metrics)
    assert len(draws) == len(cfg.ABLATIONS) * len(cfg.FILTERS) * 40
    assert set(criteria) == set(cfg.ABLATIONS)
    assert summary.decisional.sum() == len(cfg.ABLATIONS)
    assert verdict in {
        "apport démontré selon le critère préenregistré",
        "fragile : critère atteint seulement avec GPR/EPU",
        "pas d'apport démontré",
    }
