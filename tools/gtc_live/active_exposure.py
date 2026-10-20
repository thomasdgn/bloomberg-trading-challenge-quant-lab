"""Exposure comparison against a complete, operator-verified WLS weight file."""
from __future__ import annotations

from datetime import date
from typing import Any

from tools.gtc_live.ledger import DataBlocked, age_days, positive, reconcile


def compare_active_exposures(snapshot: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    """Active share and signed sector/country/currency exposure, NOT tracking error.

    Never normalize a partial index. All constituents (including non-held stocks)
    must be present, along with explicit classification and as-of metadata.
    """
    state = reconcile(snapshot)
    if not isinstance(index, dict) or index.get("verified_full_universe") is not True:
        raise DataBlocked("index: verified complete WLS membership required")
    if not str(index.get("source", "")).strip():
        raise DataBlocked("index: provenance required")
    if not isinstance(index.get("constituents"), list):
        raise DataBlocked("index: constituents list required")
    constituents = index["constituents"]
    if not constituents:
        raise DataBlocked("index: empty weights")
    expected = index.get("expected_constituent_count")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected != len(constituents):
        raise DataBlocked("index: declared constituent count does not match list")
    as_of = date.fromisoformat(state["as_of_date"])
    age_days(index.get("as_of_date"), as_of, "WLS weights", 4)
    rows = {}
    dimensions = ("sector", "country", "currency")
    for entry in constituents:
        if not isinstance(entry, dict):
            raise DataBlocked("index constituent must be an object")
        ticker = str(entry.get("id", "")).strip()
        if not ticker or ticker in rows:
            raise DataBlocked("index: blank or repeated identifier")
        weight = positive(entry.get("weight"), f"{ticker} WLS weight")
        labels = {}
        for key in dimensions:
            label = str(entry.get(key, "")).strip()
            if not label or label.lower() in {"none", "nan", "unknown"}:
                raise DataBlocked(f"{ticker}: verified {key} metadata missing")
            labels[key] = label
        rows[ticker] = {"weight": weight, **labels}
    weight_sum = sum(row["weight"] for row in rows.values())
    if abs(weight_sum - 1.0) > 1e-7:
        raise DataBlocked(f"full WLS weights must sum to 1, not {weight_sum}")
    held = {row["id"]: row["weight"] for row in state["positions"]}
    if set(held) - set(rows):
        raise DataBlocked("held stock missing from dated full WLS index")
    cash_weight = state["cash_usd"] / state["nav_usd"]
    positions = []
    groups = {dimension: {} for dimension in dimensions}
    for ticker, record in rows.items():
        benchmark_weight = record["weight"]
        portfolio_weight = held.get(ticker, 0.0)
        active = portfolio_weight - benchmark_weight
        positions.append({"id": ticker, "portfolio_weight": portfolio_weight,
                          "wls_weight": benchmark_weight, "active_weight": active})
        for dimension in dimensions:
            group = record[dimension]
            destination = groups[dimension].setdefault(
                group, {"portfolio_weight": 0.0, "wls_weight": 0.0}
            )
            destination["portfolio_weight"] += portfolio_weight
            destination["wls_weight"] += benchmark_weight
    for dimension in dimensions:
        groups[dimension]["USD_CASH"] = {
            "portfolio_weight": cash_weight, "wls_weight": 0.0
        }
        for record in groups[dimension].values():
            record["active_weight"] = (
                record["portfolio_weight"] - record["wls_weight"]
            )
    summed_active = cash_weight + sum(row["active_weight"] for row in positions)
    if abs(summed_active) > 1e-8:
        raise DataBlocked("active exposure does not sum to zero")
    active_share = 0.5 * (
        cash_weight + sum(abs(row["active_weight"]) for row in positions)
    )
    return {
        "status": "PASS", "advisory_only": True,
        "as_of_date": state["as_of_date"], "index_as_of_date": index["as_of_date"],
        "index_count": len(rows), "nav_usd": state["nav_usd"],
        "cash_weight": cash_weight, "active_share": active_share,
        "active_weight_total": summed_active,
        "top_active_positions": sorted(
            positions, key=lambda x: abs(x["active_weight"]), reverse=True
        )[:20],
        "group_exposures": groups,
        "limitations": [
            "Not tracking error or forward risk",
            "Sector/country labels describe listing classifications, not sales exposure",
            "Weights are only as reliable as the fully verified benchmark snapshot",
        ],
    }
