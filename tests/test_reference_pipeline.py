import copy
import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from scripts.run_reference import synthetic_inputs
from src.market_data import prepare_market_data
from src.optimisation import AllocationError, minimum_tracking_error
from src.risk_relative import (
    BENCHMARK,
    RelativeRiskResult,
    estimate_relative_risk,
    psd_factor,
    tracking_error_weekly,
)


def prepared(inputs=None, **kwargs):
    prices, benchmark, universe, conventions = inputs or synthetic_inputs()
    return prepare_market_data(
        prices,
        benchmark,
        universe,
        conventions,
        as_of="2026-10-07",
        cutoff="2026-10-02",
        **kwargs,
    )


def known_risk(covariance=None):
    # Independent assets, with benchmark exactly 25% A + 75% B.
    exposure = np.array([[1, 0], [0, 1], [0.25, 0.75]])
    cov = exposure @ np.diag([0.0004, 0.0009]) @ exposure.T
    cov = cov if covariance is None else covariance
    return RelativeRiskResult(
        assets=["A", "B"],
        covariance_weekly=pd.DataFrame(
            cov, index=["A", "B", BENCHMARK], columns=["A", "B", BENCHMARK]
        ),
        factor_weekly=psd_factor(cov),
        shrinkage=0,
        n_observations=52,
        observation_start="2025-10-10",
        observation_end="2026-10-02",
    )


def test_data_to_reference_end_to_end():
    data = prepared()
    risk = estimate_relative_risk(data.returns_weekly_usd, data.benchmark_returns_weekly_usd)
    result = minimum_tracking_error(risk)
    assert risk.n_observations == 52
    assert set(result.weights.index) == set(data.returns_weekly_usd.columns)
    assert result.weights.sum() == pytest.approx(1, abs=1e-8)
    assert result.weights.min() >= -1e-8
    assert result.weights.max() <= 0.18 + 1e-8
    assert (
        result.tracking_error_weekly
        <= tracking_error_weekly(risk, pd.Series(1 / 8, index=risk.assets)) + 1e-9
    )
    assert data.current_benchmark_weight_covered == pytest.approx(1)
    assert data.exclusions == {}


def test_future_prices_do_not_change_decision():
    inputs = list(synthetic_inputs())
    baseline = prepared(inputs)
    inputs[0].loc[pd.Timestamp("2026-10-09")] = 1e12
    inputs[1].loc[pd.Timestamp("2026-10-09")] = 1
    result = prepared(inputs)
    pd.testing.assert_frame_equal(result.returns_weekly_usd, baseline.returns_weekly_usd)
    pd.testing.assert_series_equal(
        result.benchmark_returns_weekly_usd, baseline.benchmark_returns_weekly_usd
    )


def test_unknown_asset_convention_is_reported_not_assumed():
    inputs = list(synthetic_inputs())
    del inputs[3]["assets"]["DEMO_0"]
    result = prepared(inputs)
    assert result.exclusions["DEMO_0"] == "unverified convention"
    assert "DEMO_0" not in result.returns_weekly_usd
    assert result.current_benchmark_weight_covered == pytest.approx(7 / 8)


@pytest.mark.parametrize(
    "field,value",
    [
        ("currency", "EUR"),
        ("adjustment", "total_return"),
        ("price_unit_multiplier", 0),
        ("available_at", "2026-10-08"),
        ("evidence", ""),
    ],
)
def test_incomplete_conventions_exclude_asset(field, value):
    inputs = list(synthetic_inputs())
    inputs[3]["assets"]["DEMO_0"][field] = value
    assert "DEMO_0" in prepared(inputs).exclusions


def test_fx_and_price_subunits_are_converted_before_returns():
    inputs = list(synthetic_inputs())
    raw = inputs[0]["DEMO_0"].copy()
    inputs[3]["assets"]["DEMO_0"].update(currency="GBP", price_unit_multiplier=0.01)
    inputs[3]["fx"] = {
        "GBP": {
            "verified": True,
            "evidence": "fixture FX",
            "available_at": "2026-10-02",
            "quote": "USD_per_unit",
        }
    }
    fx = pd.DataFrame({"GBP": np.linspace(1.1, 1.3, len(raw))}, index=raw.index)
    result = prepared(inputs, fx_usd=fx)
    expected = (raw * 0.01 * fx.GBP).pct_change(fill_method=None).iloc[1:]
    pd.testing.assert_series_equal(
        result.returns_weekly_usd["DEMO_0"], expected.rename("DEMO_0"), check_freq=False
    )


def test_missing_fx_does_not_forward_fill():
    inputs = list(synthetic_inputs())
    inputs[3]["assets"]["DEMO_0"]["currency"] = "EUR"
    inputs[3]["fx"] = {
        "EUR": {
            "verified": True,
            "evidence": "fixture",
            "available_at": "2026-10-02",
            "quote": "USD_per_unit",
        }
    }
    fx = pd.DataFrame({"EUR": 1.1}, index=inputs[0].index)
    fx.iloc[10, 0] = np.nan
    result = prepared(inputs, fx_usd=fx)
    assert len(result.returns_weekly_usd) == 50
    assert result.dropped_return_dates == ["2025-12-12", "2025-12-19"]


def test_missing_price_removes_two_returns_and_reports_dates():
    inputs = list(synthetic_inputs())
    inputs[0].iloc[10, 0] = np.nan
    result = prepared(inputs)
    assert len(result.returns_weekly_usd) == 50
    assert len(result.dropped_return_dates) == 2


def test_stale_last_price_excludes_asset():
    inputs = list(synthetic_inputs())
    # Last observation is prior Friday, not implicitly carried to cutoff.
    inputs[0].iloc[-1, 0] = np.nan
    assert "missing/stale" in prepared(inputs).exclusions["DEMO_0"]


def test_weekly_last_observation_has_explicit_age_limit():
    inputs = list(synthetic_inputs())
    dates = inputs[0].index
    new_date = dates[-1] - pd.Timedelta(days=4)
    inputs[0].loc[new_date] = np.nan
    inputs[0].loc[new_date, "DEMO_0"] = inputs[0].iloc[-2]["DEMO_0"]
    inputs[0].loc[dates[-1], "DEMO_0"] = np.nan
    inputs[0] = inputs[0].sort_index()
    assert "DEMO_0" not in prepared(inputs, max_age_days=4).exclusions
    assert "DEMO_0" in prepared(inputs, max_age_days=3).exclusions


def test_disjoint_missing_data_blocks_instead_of_pruning_assets():
    inputs = list(synthetic_inputs())
    for i in range(8):
        inputs[0].iloc[2 + 3 * i, i] = np.nan
    with pytest.raises(ValueError, match="shared complete weeks"):
        prepared(inputs)


@pytest.mark.parametrize("change", ["negative", "duplicate", "unordered", "duplicate_asset"])
def test_invalid_price_table_blocks(change):
    inputs = list(synthetic_inputs())
    if change == "negative":
        inputs[0].iloc[0, 0] = -1
    elif change == "duplicate":
        inputs[0] = pd.concat([inputs[0].iloc[:1], inputs[0]])
    elif change == "unordered":
        inputs[0] = inputs[0].iloc[::-1]
    else:
        inputs[0].columns = ["DEMO_0"] * 8
    with pytest.raises(ValueError):
        prepared(inputs)


def test_unknown_benchmark_blocks_pipeline():
    inputs = list(synthetic_inputs())
    inputs[3]["benchmark"]["verified"] = False
    with pytest.raises(ValueError, match="unverified"):
        prepared(inputs)


def test_price_and_total_return_benchmark_cannot_be_mixed():
    inputs = list(synthetic_inputs())
    inputs[3]["benchmark"]["return_type"] = "total_return"
    with pytest.raises(ValueError, match="price-return"):
        prepared(inputs)


def test_partial_universe_is_not_renormalized():
    inputs = list(synthetic_inputs())
    inputs[0] = inputs[0].iloc[:, :6]
    result = prepared(inputs)
    assert result.current_benchmark_weight_covered == pytest.approx(0.75)
    pd.testing.assert_series_equal(
        result.benchmark_returns_weekly_usd,
        inputs[1].pct_change(fill_method=None).iloc[1:].rename("WLS Index"),
        check_freq=False,
    )


def test_cutoff_must_be_completed_friday():
    with pytest.raises(ValueError, match="completed Friday"):
        prepare_market_data(*synthetic_inputs(), as_of="2026-10-02", cutoff="2026-10-02")


def test_risk_uses_one_joint_psd_estimate_and_reports_shrinkage():
    data = prepared()
    result = estimate_relative_risk(data.returns_weekly_usd, data.benchmark_returns_weekly_usd)
    assert list(result.covariance_weekly.columns) == [*result.assets, BENCHMARK]
    np.testing.assert_allclose(
        result.factor_weekly.T @ result.factor_weekly, result.covariance_weekly, atol=1e-14
    )
    assert 0 <= result.shrinkage <= 1


@pytest.mark.parametrize("change", ["nan", "inf", "dates", "duplicates"])
def test_risk_never_silently_drops_dates_or_assets(change):
    data = prepared()
    assets = data.returns_weekly_usd.copy()
    benchmark = data.benchmark_returns_weekly_usd.copy()
    if change == "nan":
        assets.iloc[0, 0] = np.nan
    elif change == "inf":
        assets.iloc[0, 0] = np.inf
    elif change == "dates":
        benchmark = benchmark.iloc[1:]
    else:
        assets.columns = ["A"] * 8
    with pytest.raises(ValueError):
        estimate_relative_risk(assets, benchmark)


def test_factor_preserves_zero_te_for_exact_replication():
    risk = known_risk()
    assert tracking_error_weekly(risk, pd.Series({"B": 0.75, "A": 0.25})) < 1e-9
    result = minimum_tracking_error(risk, max_weight=1)
    np.testing.assert_allclose(result.weights, [0.25, 0.75], atol=1e-6)
    assert result.tracking_error_weekly < 1e-8


def test_analytic_constrained_optimum_and_infeasible_te():
    risk = known_risk()
    result = minimum_tracking_error(risk, max_weight=pd.Series({"B": 0.6, "A": 0.9}))
    np.testing.assert_allclose(result.weights, [0.4, 0.6], atol=1e-6)
    assert result.tracking_error_weekly == pytest.approx(0.15 * np.sqrt(0.0013), abs=1e-8)
    with pytest.raises(AllocationError, match="exceeds ceiling"):
        minimum_tracking_error(risk, max_weight=0.6, max_tracking_error_weekly=0.001)


def test_infeasible_caps_and_exposures_block():
    with pytest.raises(AllocationError, match="caps"):
        minimum_tracking_error(known_risk(), max_weight=0.18)
    with pytest.raises(AllocationError, match="infeasible"):
        minimum_tracking_error(
            known_risk(),
            max_weight=1,
            exposures=pd.DataFrame({"sector": [0, 0]}, index=["A", "B"]),
            exposure_bounds={"sector": (0.2, 0.5)},
        )


def test_exposure_limits_and_identifier_alignment():
    result = minimum_tracking_error(
        known_risk(),
        max_weight=1,
        exposures=pd.DataFrame({"sector": [0, 1]}, index=["B", "A"]),
        exposure_bounds={"sector": (0.35, 0.5)},
    )
    assert result.weights.A == pytest.approx(0.35, abs=1e-6)
    assert result.exposure_values["sector"] == pytest.approx(0.35, abs=1e-6)
    assert result.max_constraint_violation < 1e-8


def test_permutation_preserves_identifier_weights():
    risk = known_risk()
    labels = ["B", "A", BENCHMARK]
    permuted = copy.copy(risk)
    object.__setattr__(permuted, "assets", ["B", "A"])
    object.__setattr__(permuted, "covariance_weekly", risk.covariance_weekly.loc[labels, labels])
    original = minimum_tracking_error(risk, max_weight=0.6)
    result = minimum_tracking_error(permuted, max_weight=0.6)
    pd.testing.assert_series_equal(
        result.weights.reindex(original.weights.index), original.weights, atol=1e-7
    )


def test_non_psd_or_asymmetric_covariance_blocks():
    with pytest.raises(ValueError, match="positive semidefinite"):
        psd_factor(np.array([[1, 2], [2, 1]]))
    with pytest.raises(ValueError, match="symmetric"):
        psd_factor(np.array([[1, 0], [1, 1]]))


def test_inaccurate_solver_result_is_rejected(monkeypatch):
    def fake_solve(problem, **kwargs):
        problem._status = "optimal_inaccurate"

    monkeypatch.setattr("cvxpy.Problem.solve", fake_solve)
    with pytest.raises(AllocationError, match="optimal_inaccurate"):
        minimum_tracking_error(known_risk(), max_weight=1)


def test_independent_check_rejects_invalid_optimal_weights(monkeypatch):
    def fake_solve(problem, **kwargs):
        problem._status = "optimal"
        problem.variables()[0].value = np.array([0.7, 0.7])

    monkeypatch.setattr("cvxpy.Problem.solve", fake_solve)
    with pytest.raises(AllocationError, match="constraint check"):
        minimum_tracking_error(known_risk(), max_weight=1)


def test_cli_demo_writes_research_report_and_cannot_overwrite(tmp_path):
    destination = tmp_path / "run"
    command = [
        sys.executable,
        "-m",
        "scripts.run_reference",
        "--demo",
        "--output",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "reference_computed"
    assert report["ready_for_trading"] is False
    assert report["synthetic"] is True
    assert (destination / "reference_weights.csv").exists()
    again = subprocess.run(command, capture_output=True, text=True)
    assert again.returncode == 2


def test_cli_blocked_run_has_no_weight_export(tmp_path):
    destination = tmp_path / "blocked"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.run_reference",
            "--demo",
            "--max-weight",
            "0.01",
            "--output",
            str(destination),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stderr
    report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert not (destination / "reference_weights.csv").exists()


def test_cli_reads_export_files_and_records_provenance(tmp_path):
    prices, benchmark, universe, conventions = synthetic_inputs()
    root = tmp_path / "data"
    root.mkdir()
    prices.to_csv(root / "prices_10y.csv.gz", index_label="date")
    benchmark.rename("px_last").to_csv(root / "benchmark_10y.csv", index_label="date")
    universe.to_csv(root / "universe.csv", index=False)
    candidates = tmp_path / "candidates.csv"
    universe[["id"]].to_csv(candidates, index=False)
    metadata = tmp_path / "conventions.json"
    metadata.write_text(json.dumps(conventions), encoding="utf-8")
    destination = tmp_path / "reference"
    command = [
        sys.executable,
        "-m",
        "scripts.run_reference",
        "--input",
        str(root),
        "--candidates",
        str(candidates),
        "--conventions",
        str(metadata),
        "--as-of",
        "2026-10-07",
        "--cutoff",
        "2026-10-02",
        "--output",
        str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "reference_computed"
    assert report["ready_for_trading"] is False
    assert set(report["source_sha256"]) == {
        "prices",
        "benchmark",
        "universe",
        "conventions",
        "candidates",
    }
    assert len(report["code_sha256"]) == 5
    assert report["package_versions"]["clarabel"]
    conventions["benchmark"]["verified"] = False
    metadata.write_text(json.dumps(conventions), encoding="utf-8")
    command[-1] = str(tmp_path / "unverified")
    blocked = subprocess.run(command, capture_output=True, text=True)
    assert blocked.returncode == 2
    assert not (tmp_path / "unverified" / "reference_weights.csv").exists()


def test_invalid_axes_are_checked_before_cutoff_slicing():
    inputs = list(synthetic_inputs())
    inputs[0] = inputs[0].iloc[::-1]
    with pytest.raises(ValueError, match="sorted"):
        prepared(inputs)
