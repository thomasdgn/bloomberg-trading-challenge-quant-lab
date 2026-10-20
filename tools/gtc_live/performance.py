"""Daily WLS-relative attribution for unchanged executed positions (no invented fills)."""

from __future__ import annotations

from typing import Any

from tools.gtc_live.ledger import DataBlocked, positive, reconcile


def _verified_benchmark(entry: dict[str, Any], expected_date: str) -> float:
    if not isinstance(entry, dict) or entry.get("verified") is not True:
        raise DataBlocked("benchmark: explicit verified level required")
    if entry.get("as_of_date") != expected_date:
        raise DataBlocked("benchmark: observation date does not match portfolio")
    if entry.get("basis") != "PRICE_RETURN":
        raise DataBlocked("benchmark: define and confirm common PRICE_RETURN basis")
    if not str(entry.get("source", "")).strip():
        raise DataBlocked("benchmark: provenance required")
    return positive(entry.get("level"), "benchmark level")


def daily_relative_pnl(
    start: dict[str, Any],
    end: dict[str, Any],
    benchmark_start: dict[str, Any],
    benchmark_end: dict[str, Any],
) -> dict[str, Any]:
    """Only supports no-trade, no-external-flow close-to-close days.

    Reject share count changes, changing cash and mixed return bases. The
    1-day active contribution includes the implicit benchmark allocation of cash.
    """
    first = reconcile(start)
    last = reconcile(end)
    if first["as_of_date"] >= last["as_of_date"]:
        raise DataBlocked("portfolio dates must be increasing")
    if first["pending_orders"] or last["pending_orders"]:
        raise DataBlocked("unreconciled pending orders: no-trade attribution blocked")
    if abs(first["cash_usd"] - last["cash_usd"]) > max(1e-8, first["nav_usd"] * 1e-10):
        raise DataBlocked("cash changed: supply fills and cash flows before attribution")
    start_qty = {p["id"]: p["quantity"] for p in first["positions"]}
    end_qty = {p["id"]: p["quantity"] for p in last["positions"]}
    if start_qty != end_qty:
        raise DataBlocked("holdings changed: cannot assume a daily no-trade return")
    b0 = _verified_benchmark(benchmark_start, first["as_of_date"])
    b1 = _verified_benchmark(benchmark_end, last["as_of_date"])
    br = b1 / b0 - 1.0
    pr = last["nav_usd"] / first["nav_usd"] - 1.0
    contrib = []
    for ticker, qty in sorted(start_qty.items()):
        start_usd = first["instruments"][ticker]["price_usd"]
        end_usd = last["instruments"][ticker]["price_usd"]
        start_value = qty * start_usd
        absolute = qty * (end_usd - start_usd)
        active = absolute / first["nav_usd"] - start_value / first["nav_usd"] * br
        contrib.append(
            {
                "id": ticker,
                "price_return_usd": end_usd / start_usd - 1,
                "start_weight": start_value / first["nav_usd"],
                "pnl_usd": absolute,
                "active_contribution": active,
            }
        )
    cash_active = -(first["cash_usd"] / first["nav_usd"]) * br
    total_active = sum(item["active_contribution"] for item in contrib) + cash_active
    if abs(total_active - (pr - br)) > 1e-10:
        raise DataBlocked("attribution failed reconciliation identity")
    return {
        "status": "PASS",
        "advisory_only": True,
        "start_date": first["as_of_date"],
        "end_date": last["as_of_date"],
        "portfolio_return": pr,
        "benchmark_return": br,
        "active_return": pr - br,
        "pnl_usd": last["nav_usd"] - first["nav_usd"],
        "cash_active_contribution": cash_active,
        "contributions": sorted(contrib, key=lambda x: x["active_contribution"]),
        "limitation": "Only unchanged executed quantities and unchanged cash; no fills/flows",
    }
