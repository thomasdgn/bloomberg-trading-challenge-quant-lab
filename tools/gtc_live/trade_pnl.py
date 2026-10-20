"""Fill-aware two-snapshot P&L: only confirmed execution events count.

All effects measured in verified USD marks. No orders are sent. No external flows,
dividends, splits, FX financing or interim time-weighted returns are supported.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from math import isclose
from typing import Any

from tools.gtc_live.ledger import DataBlocked, positive, reconcile
from tools.gtc_live.performance import _verified_benchmark


def _aware_time(raw: Any, lower: date, upper: date) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DataBlocked("fill executed_at: ISO time with timezone required") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise DataBlocked("fill executed_at must include timezone")
    stamp_utc = stamp.astimezone(timezone.utc)
    if not lower < stamp_utc.date() <= upper:
        raise DataBlocked("fill executed_at outside close-to-close interval")
    return stamp_utc


def reconcile_filled_pnl(
    start: dict[str, Any],
    end: dict[str, Any],
    fills: list[dict[str, Any]],
    benchmark_start: dict[str, Any],
    benchmark_end: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct end holdings/cash from start + UTC-ordered confirmed fills.

    The resulting P&L is a simple NAV-relative return. Fills must include all
    execution fees and conversion to USD at time of execution. If external cash
    flows, dividends, corporate actions or unreconciled fills exist, BLOCK.
    """
    before = reconcile(start)
    after = reconcile(end)
    start_date = date.fromisoformat(before["as_of_date"])
    end_date = date.fromisoformat(after["as_of_date"])
    if not start_date < end_date:
        raise DataBlocked("snapshot dates must strictly increase")
    if not isinstance(fills, list):
        raise DataBlocked("fills: explicit confirmed list required")
    expected_quantities = {p["id"]: p["quantity"] for p in before["positions"]}
    target_quantities = {p["id"]: p["quantity"] for p in after["positions"]}
    expected_cash = before["cash_usd"]
    entries = []
    trade_changes = {}
    observed_ids = set()
    last_time = None
    for item in fills:
        if not isinstance(item, dict) or item.get("status") != "FILLED":
            raise DataBlocked("every event must be a confirmed FILLED execution")
        fill_id = str(item.get("fill_id", "")).strip()
        if not fill_id or fill_id in observed_ids:
            raise DataBlocked("unique fill_id required")
        observed_ids.add(fill_id)
        instant = _aware_time(item.get("executed_at"), start_date, end_date)
        if last_time is not None and instant < last_time:
            raise DataBlocked("fills must be in ascending UTC execution-time order")
        last_time = instant
        ticker = str(item.get("id", "")).strip()
        if ticker not in before["instruments"] or ticker not in after["instruments"]:
            raise DataBlocked(f"{ticker}: missing verified marks at both snapshots")
        side = str(item.get("side", "")).upper()
        if side not in {"BUY", "SELL"}:
            raise DataBlocked(f"{fill_id}: invalid side")
        quantity = positive(item.get("quantity"), f"{fill_id} quantity")
        price = positive(item.get("execution_price_local"), f"{fill_id} execution price")
        unit = positive(item.get("price_unit_multiplier"), f"{fill_id} multiplier")
        fx = positive(item.get("usd_per_unit"), f"{fill_id} FX")
        fee = positive(item.get("fee_usd"), f"{fill_id} fee", zero_ok=True)
        currency = str(item.get("currency", "")).upper()
        if currency != before["instruments"][ticker]["currency"]:
            raise DataBlocked(f"{fill_id}: fill currency and source mark differ")
        if currency == "USD" and not isclose(fx, 1.0, abs_tol=1e-10):
            raise DataBlocked(f"{fill_id}: USD FX must be one")
        if currency != "USD":
            # Exact executed FX timestamp is mandatory for foreign-currency fills.
            fx_time = _aware_time(item.get("fx_observed_at"), start_date, end_date)
            if fx_time > instant:
                raise DataBlocked(f"{fill_id}: FX timestamp cannot follow execution")
        value = quantity * price * unit * fx
        if side == "BUY":
            expected_cash -= value + fee
            expected_quantities[ticker] = expected_quantities.get(ticker, 0.0) + quantity
        else:
            available = expected_quantities.get(ticker, 0.0)
            if quantity > available + 1e-9:
                raise DataBlocked(f"{fill_id}: sale exceeds confirmed holdings")
            expected_cash += value - fee
            expected_quantities[ticker] = available - quantity
        sign = 1 if side == "BUY" else -1
        end_mark = after["instruments"][ticker]["price_usd"]
        trade_changes[ticker] = trade_changes.get(ticker, 0.0) + (
            sign * quantity * (end_mark - price * unit * fx) - fee
        )
        entries.append({"fill_id": fill_id, "id": ticker, "side": side,
                        "quantity": quantity, "fill_notional_usd": value,
                        "fee_usd": fee, "executed_at_utc": instant.isoformat()})
    for ticker in set(expected_quantities) | set(target_quantities):
        if not isclose(expected_quantities.get(ticker, 0.0),
                       target_quantities.get(ticker, 0.0), abs_tol=1e-8):
            raise DataBlocked(f"{ticker}: executed fill quantities do not reconcile")
    tolerance = max(0.01, before["nav_usd"] * 1e-8)
    if abs(expected_cash - after["cash_usd"]) > tolerance:
        raise DataBlocked("settled cash does not reconcile to reported executed fills")
    b0 = _verified_benchmark(benchmark_start, before["as_of_date"])
    b1 = _verified_benchmark(benchmark_end, after["as_of_date"])
    active = after["nav_usd"] / before["nav_usd"] - 1 - (b1 / b0 - 1)
    contributors = []
    for ticker in sorted(set(expected_quantities) | set(target_quantities)):
        if ticker not in before["instruments"] or ticker not in after["instruments"]:
            raise DataBlocked(f"{ticker}: missing original/end mark")
        start_qty = next((p["quantity"] for p in before["positions"] if p["id"] == ticker), 0.0)
        price_delta = (after["instruments"][ticker]["price_usd"]
                       - before["instruments"][ticker]["price_usd"])
        pnl = start_qty * price_delta + trade_changes.get(ticker, 0.0)
        contributors.append({"id": ticker, "pnl_usd": pnl,
                             "portfolio_contribution": pnl / before["nav_usd"]})
    total = sum(r["pnl_usd"] for r in contributors)
    if abs(total - (after["nav_usd"] - before["nav_usd"])) > tolerance:
        raise DataBlocked("trade-aware P&L contributors fail reconciliation")
    return {
        "status": "PASS", "advisory_only": True,
        "start_date": before["as_of_date"], "end_date": after["as_of_date"],
        "fills_reconciled": len(entries), "fills": entries,
        "nav_start_usd": before["nav_usd"], "nav_end_usd": after["nav_usd"],
        "pnl_usd": total, "portfolio_return": total / before["nav_usd"],
        "benchmark_return": b1 / b0 - 1, "active_return": active,
        "pnl_contributors": contributors,
        "limitation": "Simple period return; no external flows, dividends or corporate actions",
    }
