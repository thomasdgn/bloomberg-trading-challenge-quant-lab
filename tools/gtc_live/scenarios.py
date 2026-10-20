"""Transparent deterministic stress tests, not predictive probabilities."""

from __future__ import annotations

from math import isfinite
from typing import Any

from tools.gtc_live.ledger import DataBlocked, reconcile


def stress_portfolio(
    snapshot: dict[str, Any], scenarios: dict[str, dict[str, float]]
) -> dict[str, Any]:
    """User-declared per-security USD shocks. No guessed correlation or missing shocks."""
    state = reconcile(snapshot)
    if not isinstance(scenarios, dict) or not scenarios:
        raise DataBlocked("at least one named scenario required")
    positions = state["positions"]
    results = []
    for scenario_name, shocks in scenarios.items():
        if not str(scenario_name).strip() or not isinstance(shocks, dict):
            raise DataBlocked("scenario name and mapping required")
        ids = {p["id"] for p in positions}
        if set(shocks) != ids:
            raise DataBlocked(f"{scenario_name}: shock every held id exactly once")
        losses = []
        for item in positions:
            raw = shocks[item["id"]]
            if isinstance(raw, bool):
                raise DataBlocked("shock cannot be boolean")
            try:
                shock = float(raw)
            except (TypeError, ValueError) as exc:
                raise DataBlocked(f"{item['id']}: numeric shock required") from exc
            if not isfinite(shock) or shock < -1.0:
                raise DataBlocked(f"{item['id']}: finite shock >= -100% required")
            losses.append(
                {"id": item["id"], "shock": shock, "pnl_usd": item["market_value_usd"] * shock}
            )
        pnl_usd = sum(row["pnl_usd"] for row in losses)
        results.append(
            {
                "name": scenario_name,
                "portfolio_pnl_usd": pnl_usd,
                "portfolio_return": pnl_usd / state["nav_usd"],
                "per_position": losses,
            }
        )
    return {
        "status": "PASS",
        "advisory_only": True,
        "as_of_date": state["as_of_date"],
        "nav_usd": state["nav_usd"],
        "scenarios": results,
        "note": ("Hypothetical USD mark shocks only; no liquidity, correlation or fill modelling"),
    }
