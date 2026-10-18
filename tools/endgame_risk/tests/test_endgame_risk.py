"""Synthetic data only: no macro research or real portfolio calculations."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.covariance import estimate_ledoit_wolf
from tools.endgame_risk.analytics import attribution, homogeneous, rule_violations, targeted
from tools.endgame_risk.data import DataBlocked, earnings_calendar, load_inputs
from tools.endgame_risk.run import main


@pytest.fixture
def market(tmp_path):
    rng = np.random.default_rng(91)
    dates = pd.bdate_range("2025-01-01", "2026-10-16")
    prices = pd.DataFrame(
        {
            "A": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates)))),
            "B": 80 * np.exp(np.cumsum(rng.normal(0, 0.012, len(dates)))),
        },
        index=dates,
    )
    prices.index.name = "date"
    prices.to_csv(tmp_path / "prices.csv")
    fx = pd.DataFrame(
        {
            "date": dates,
            "currency": "EUR",
            "usd_rate": np.exp(np.cumsum(rng.normal(0, 0.004, len(dates)))),
        }
    )
    fx.to_csv(tmp_path / "fx.csv", index=False)
    pd.DataFrame(
        {
            "id": ["A", "B"],
            "currency": ["USD", "EUR"],
            "sector": ["TECH", "HEALTH"],
            "country": ["US", "DE"],
            "price_unit_multiplier": [1, 1],
        }
    ).to_csv(tmp_path / "meta.csv", index=False)
    pd.DataFrame({"id": ["A", "B"], "index_weight": [0.6, 0.4]}).to_csv(
        tmp_path / "wls.csv", index=False
    )
    config = {
        "conventions_verified": True,
        "convention_source": "synthetic test fixture",
        "available_at": "2026-10-16",
        "return_basis": "split_adjusted_price",
        "prices": "prices.csv",
        "fx": "fx.csv",
        "metadata": "meta.csv",
        "benchmark_weights": "wls.csv",
        "benchmark_snapshot_date": "2026-10-16",
    }
    portfolio = {
        "as_of_date": "2026-10-18",
        "status": "executed",
        "positions": [
            {"id": "A", "quantity": 10, "currency": "USD"},
            {"id": "B", "quantity": 12, "currency": "EUR"},
        ],
        "cash": [{"currency": "USD", "amount": 1000}, {"currency": "EUR", "amount": 500}],
    }
    pp, cp = tmp_path / "portfolio.json", tmp_path / "config.json"
    pp.write_text(json.dumps(portfolio))
    cp.write_text(json.dumps(config))
    return tmp_path, pp, cp, prices, fx


def test_valuation_historical_fx_and_existing_estimator(market):
    _, pp, cp, prices, fx = market
    inputs = load_inputs(pp, cp)
    latest = prices.iloc[-1]
    rate = fx.usd_rate.iloc[-1]
    nav = latest.A * 10 + latest.B * rate * 12 + 1000 + 500 * rate
    assert np.isclose(inputs.provenance["nav_usd"], nav)
    assert np.isclose(inputs.weights["B"], latest.B * rate * 12 / nav)
    usd = prices.copy()
    rates = fx.set_index("date").usd_rate
    usd["B"] *= rates
    usd["CASH:EUR"] = rates
    returns = usd.resample("W-FRI").last().tail(53).pct_change(fill_method=None).iloc[1:]
    reference = estimate_ledoit_wolf(returns, min_observations=40)
    pd.testing.assert_frame_equal(
        inputs.covariance.loc[reference.assets, reference.assets], reference.covariance_weekly
    )
    assert inputs.covariance.loc["CASH:USD"].eq(0).all()
    assert inputs.provenance["wls_weight_covered"] == 1


def test_truncation_no_future_prices_fx_or_conventions(market):
    root, pp, cp, prices, fx = market
    before = load_inputs(pp, cp)
    prices.loc[pd.Timestamp("2026-10-19")] = [1e8, 1e9]
    prices.to_csv(root / "prices.csv")
    fx.loc[len(fx)] = [pd.Timestamp("2026-10-19"), "EUR", 1000]
    fx.to_csv(root / "fx.csv", index=False)
    after = load_inputs(pp, cp)
    pd.testing.assert_series_equal(before.weights, after.weights)
    pd.testing.assert_frame_equal(before.covariance, after.covariance)
    config = json.loads(cp.read_text())
    config["available_at"] = "2026-10-19"
    cp.write_text(json.dumps(config))
    with pytest.raises(DataBlocked, match="available"):
        load_inputs(pp, cp)


@pytest.mark.parametrize("fault", ["history", "country", "fx_history", "snapshot", "pending"])
def test_missing_inputs_block_without_proxy_or_pruning(market, fault):
    root, pp, cp, prices, fx = market
    if fault == "history":
        prices.drop(columns="B").to_csv(root / "prices.csv")
    elif fault == "country":
        meta = pd.read_csv(root / "meta.csv")
        meta.loc[0, "country"] = None
        meta.to_csv(root / "meta.csv", index=False)
    elif fault == "fx_history":
        fx.tail(1).to_csv(root / "fx.csv", index=False)
    elif fault == "snapshot":
        config = json.loads(cp.read_text())
        config["benchmark_snapshot_date"] = "2026-10-07"
        cp.write_text(json.dumps(config))
    else:
        portfolio = json.loads(pp.read_text())
        portfolio["orders_pending"] = [{"id": "A", "budget_usd": 100}]
        pp.write_text(json.dumps(portfolio))
    with pytest.raises(DataBlocked):
        load_inputs(pp, cp)


def test_cash_weight_units_and_no_mixed_modes(market):
    _, pp, cp, _, _ = market
    portfolio = json.loads(pp.read_text())
    portfolio["positions"] = [{"id": "A", "weight": 0.4}, {"id": "B", "weight": 0.3}]
    portfolio["cash"] = [{"currency": "USD", "weight": 0.3}]
    pp.write_text(json.dumps(portfolio))
    inputs = load_inputs(pp, cp)
    assert inputs.weights["CASH:USD"] == 0.3
    assert inputs.provenance["nav_usd"] is None
    portfolio["cash"] = [{"currency": "USD", "amount": 1000}]
    pp.write_text(json.dumps(portfolio))
    with pytest.raises(DataBlocked, match="mix"):
        load_inputs(pp, cp)


def test_euler_groups_and_homogeneous_factors(market):
    _, pp, cp, _, _ = market
    x = load_inputs(pp, cp)
    te, table, groups, top = attribution(x.weights, x.benchmark, x.covariance, x.metadata)
    assert np.isclose(table.total_te_contribution.sum(), te)
    assert all(np.isclose(group.sum(), te) for group in groups.values())
    assert len(top) == len(x.weights)
    for result in homogeneous(x.weights, x.benchmark, x.covariance, x.metadata):
        assert np.isclose(result["annual_te_theoretical"], result["active_weight_factor"] * te)
        assert result["challenge_constraints"] == "not_supplied"
    zero = attribution(x.benchmark, x.benchmark, x.covariance, x.metadata)
    assert zero[0] == 0 and zero[1].total_te_contribution.eq(0).all()


def small_model(two_sales=False):
    names = ["A", "B", "C", "CASH:USD"] if two_sales else ["A", "B", "CASH:USD"]
    weights = pd.Series([0.5, 0.5, 0, 0] if two_sales else [0.8, 0, 0.2], index=names)
    bm = pd.Series([0, 0, 1, 0] if two_sales else [0.5, 0.5, 0], index=names)
    diag = [0.01, 0.01, 0.0001, 0] if two_sales else [0.01, 0.0001, 0]
    cov = pd.DataFrame(np.diag(diag), index=names, columns=names)
    meta = pd.DataFrame({"sector": "TECH", "country": "US", "currency": "USD"}, index=names)
    return weights, bm, cov, meta


@pytest.mark.parametrize("two_sales", [False, True])
def test_targeted_minimum_cardinality_and_cash_conservation(two_sales):
    weights, bm, cov, meta = small_model(two_sales)
    output = targeted(weights, bm, cov, meta)
    assert output["status"] == "minimum_proven_to_tolerance"
    assert output["transactions"] == (2 if two_sales else 1)
    baseline = attribution(weights, bm, cov, meta)[0]
    assert output["annual_te"] <= baseline / 2 + 1e-7
    simulated = weights.copy()
    for row in output["reductions"]:
        assert row["weight_reduction"] > 0
        simulated[row["id"]] -= row["weight_reduction"]
        simulated["CASH:USD"] += row["weight_reduction"]
    assert np.isclose(simulated.sum(), 1)
    assert simulated.min() >= -1e-10


def test_infeasible_sales_and_search_limit_are_explicit():
    w, b, c, m = small_model()
    w[:] = [1, 0, 0]
    b[:] = [0.2, 0.8, 0]
    c.loc["B", "B"] = 0.01
    assert targeted(w, b, c, m)["status"] == "infeasible_sales_only"
    w, b, c, m = small_model(True)
    assert targeted(w, b, c, m, max_subsets=1)["status"] == "search_limit_minimum_not_proven"


def test_increase_flags_shorting_and_checks_supplied_rules():
    w, b, c, m = small_model()
    result = homogeneous(w, b, c, m)[-1]
    assert not result["basic_feasible"] and "negative_weight" in result["violations"]
    rules = {"source": "synthetic regulation", "max_weight": 0.7, "sector_caps": {"TECH": 0.9}}
    assert "max_weight" in rule_violations(w, m, rules)
    with pytest.raises(ValueError, match="Unsupported"):
        rule_violations(w, m, {"source": "test", "unknown_clause": 1})


def test_earnings_known_as_of_and_horizon_only(market):
    _, pp, cp, _, _ = market
    x = load_inputs(pp, cp)
    x.earnings = pd.DataFrame(
        {
            "id": ["A", "B", "B"],
            "event_date": pd.to_datetime(["2026-11-01", "2026-11-02", "2026-11-14"]),
            "available_at": pd.to_datetime(["2026-10-17", "2026-10-19", "2026-10-17"]),
            "source": "synthetic",
            "status": "expected",
        }
    )
    events = earnings_calendar(x).set_index("id")
    assert events.loc["A", "event_date"] == "2026-11-01"
    assert events.loc["B", "status"] == "not_available_in_supplied_data"


def test_cli_blocks_pending_without_risk_or_order_files(market):
    root, pp, cp, _, _ = market
    from tools.endgame_risk import run

    previous = run.ROOT
    run.ROOT = root
    try:
        portfolio = json.loads(pp.read_text())
        portfolio["status"] = "pending"
        pp.write_text(json.dumps(portfolio))
        # The CLI records a core hash: supply an unchanged copy inside this synthetic tree.
        (root / "src").mkdir()
        (root / "src/covariance.py").write_bytes((previous / "src/covariance.py").read_bytes())
        destination = root / "outputs/blocked"
        # Provenance commit lookup is mocked, not a Git mutation or research execution.
        from unittest.mock import patch

        with patch("tools.endgame_risk.run.subprocess.check_output", return_value="testcommit\n"):
            assert (
                main(
                    [
                        "--portfolio",
                        str(pp),
                        "--market-config",
                        str(cp),
                        "--output-dir",
                        str(destination),
                    ]
                )
                == 2
            )
        manifest = json.loads((destination / "run_manifest.json").read_text())
        assert manifest["status"] == "blocked" and "annual_te" not in manifest
        assert sorted(p.name for p in destination.iterdir()) == ["RAPPORT.md", "run_manifest.json"]
    finally:
        run.ROOT = previous


def test_cli_computes_complete_synthetic_flow(market, monkeypatch):
    root, pp, cp, _, _ = market
    from tools.endgame_risk import run

    monkeypatch.setattr(run, "ROOT", root)
    (root / "src").mkdir()
    source = Path(__file__).resolve().parents[3] / "src/covariance.py"
    (root / "src/covariance.py").write_bytes(source.read_bytes())
    monkeypatch.setattr(run.subprocess, "check_output", lambda *args, **kwargs: "synthetic\n")
    destination = root / "outputs/complete"
    assert (
        main(["--portfolio", str(pp), "--market-config", str(cp), "--output-dir", str(destination)])
        == 0
    )
    manifest = json.loads((destination / "run_manifest.json").read_text())
    assert manifest["status"] == "computed" and manifest["annual_te"] > 0
    assert len(manifest["homogeneous"]) == 3
    assert {p.name for p in destination.iterdir()} == {
        "RAPPORT.md",
        "run_manifest.json",
        "contributions.csv",
        "valuation.csv",
        "earnings.csv",
    }


def test_csv_positions_and_price_subunits(market):
    root, pp, cp, _, _ = market
    before = load_inputs(pp, cp)
    portfolio = json.loads(pp.read_text())
    pd.DataFrame(portfolio.pop("positions")).to_csv(root / "positions.csv", index=False)
    portfolio["positions_file"] = "positions.csv"
    pp.write_text(json.dumps(portfolio))
    meta = pd.read_csv(root / "meta.csv")
    meta["price_unit_multiplier"] = meta.price_unit_multiplier.astype(float)
    meta.loc[meta.id.eq("B"), "price_unit_multiplier"] = 0.01
    meta.to_csv(root / "meta.csv", index=False)
    p = pd.read_csv(root / "prices.csv")
    p["B"] *= 100
    p.to_csv(root / "prices.csv", index=False)
    after = load_inputs(pp, cp)
    pd.testing.assert_series_equal(before.weights, after.weights)
    assert np.allclose(before.covariance, after.covariance)
    assert "positions_file_sha256" in after.provenance


def test_cash_must_be_explicit_even_for_fully_invested_portfolio(market):
    _, pp, cp, _, _ = market
    portfolio = json.loads(pp.read_text())
    portfolio["cash"] = []
    pp.write_text(json.dumps(portfolio))
    with pytest.raises(DataBlocked, match="cash"):
        load_inputs(pp, cp)


def test_negative_risk_contributions_are_retained():
    w, b, c, m = small_model()
    c.loc["A", "B"] = c.loc["B", "A"] = 0.0008
    te, rows, groups, _ = attribution(w, b, c, m)
    assert rows.total_te_contribution.min() < 0
    assert np.isclose(rows.total_te_contribution.sum(), te)
    assert np.isclose(groups["sector"].sum(), te)


def test_numerical_failure_never_proves_infeasibility(monkeypatch):
    from types import SimpleNamespace

    from tools.endgame_risk import analytics

    monkeypatch.setattr(
        analytics, "minimize", lambda fun, x, **kw: SimpleNamespace(x=np.full_like(x, np.nan))
    )
    w, b, c, m = small_model()
    assert targeted(w, b, c, m)["status"] == "unresolved_numerically"
