"""Conservative PRE-TRADE checks. Never place an order or recycle unfilled sells."""
from __future__ import annotations

from typing import Any

from tools.gtc_live.ledger import DataBlocked, positive, reconcile


def check_trade_plan(
    snapshot: dict[str, Any],
    proposals: list[dict[str, Any]],
    *,
    max_position_weight: float = 0.20,
    internal_warning_weight: float = 0.18,
    execution_buffer_bps: float = 20.0,
) -> dict[str, Any]:
    """Reject unsafe candidate orders; returns *advisory* risk report only.

    A buy is reserved against cash at the worse of mark and limit plus execution buffer.
    Pending sells do not release cash or concentration until genuinely filled.
    """
    if not 0 < max_position_weight <= 0.20:
        raise DataBlocked("max_position_weight must be in (0, 0.20]")
    if not 0 < internal_warning_weight <= max_position_weight:
        raise DataBlocked("internal warning weight cannot exceed regulatory cap")
    buffer = positive(execution_buffer_bps, "execution_buffer_bps", zero_ok=True) / 10_000
    if not isinstance(proposals, list):
        raise DataBlocked("proposals: explicit list required")
    state = reconcile(snapshot)
    instruments = state["instruments"]
    marks = {p["id"]: p["market_value_usd"] for p in state["positions"]}
    held = {p["id"]: p["quantity"] for p in state["positions"]}
    pending_buys = state["pending_buy_quantity"]
    pending_sells = state["pending_sell_quantity"]
    nav = state["nav_usd"]
    warnings = []
    for ticker, value in marks.items():
        if value / nav > max_position_weight + 1e-9:
            raise DataBlocked(f"{ticker}: executed weight above regulatory cap")
        if value / nav > internal_warning_weight:
            warnings.append(f"{ticker}: executed weight above internal warning")
    pending_buy_values = {
        order["id"]: 0.0 for order in state["pending_orders"] if order["side"] == "BUY"
    }
    for order in state["pending_orders"]:
        if order["side"] == "BUY":
            ticker = order["id"]
            unit = max(float(order["limit_price_usd"]), instruments[ticker]["price_usd"])
            pending_buy_values[ticker] += order["remaining_quantity"] * unit
    for ticker, pending_usd in pending_buy_values.items():
        if (marks.get(ticker, 0) + pending_usd) / nav > max_position_weight + 1e-9:
            raise DataBlocked(f"{ticker}: cap breached by pending buys")
    order_ids = set()
    planned_buy_value = {}
    planned_sell_qty = {}
    accepted = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            raise DataBlocked("proposal: object required")
        oid = str(proposal.get("client_id", "")).strip()
        if not oid or oid in order_ids:
            raise DataBlocked("proposal: unique client_id required")
        order_ids.add(oid)
        ticker = str(proposal.get("id", "")).strip()
        if ticker not in instruments:
            raise DataBlocked(f"{ticker}: missing verified WLS instrument and quote")
        side = str(proposal.get("side", "")).upper()
        if side not in {"BUY", "SELL"}:
            raise DataBlocked(f"{oid}: BUY or SELL required")
        qty = positive(proposal.get("quantity"), f"{oid} quantity")
        if side == "BUY":
            if ticker in pending_buys or ticker in pending_sells:
                raise DataBlocked(f"{ticker}: pending order; reconcile before another buy")
            unit = instruments[ticker]["price_usd"]
            if "limit_price_local" in proposal:
                raw = next(x for x in snapshot["instruments"] if x["id"] == ticker)
                limit = positive(proposal["limit_price_local"], f"{oid} limit")
                unit = max(unit, limit * float(raw["price_unit_multiplier"]) *
                           float(raw["usd_per_unit"]))
            planned_buy_value[ticker] = planned_buy_value.get(ticker, 0.0) + qty * unit
        else:
            if ticker in pending_buys:
                raise DataBlocked(f"{ticker}: pending buy; reconcile before selling")
            planned_sell_qty[ticker] = planned_sell_qty.get(ticker, 0.0) + qty
        accepted.append({"client_id": oid, "id": ticker, "side": side, "quantity": qty})
    for ticker, qty in planned_sell_qty.items():
        if qty + pending_sells.get(ticker, 0.0) > held.get(ticker, 0.0) + 1e-9:
            raise DataBlocked(f"{ticker}: proposed and pending sells exceed executed shares")
    planned_cost = sum(planned_buy_value.values()) * (1 + buffer)
    if planned_cost > state["available_cash_usd"] + max(1e-8, nav * 1e-9):
        raise DataBlocked("proposed buys plus pending orders exceed settled buying power")
    for ticker in set(marks) | set(planned_buy_value) | set(pending_buy_values):
        exposure = marks.get(ticker, 0) + planned_buy_value.get(ticker, 0)
        exposure += pending_buy_values.get(ticker, 0)
        projected_weight = exposure / nav
        if projected_weight > max_position_weight + 1e-9:
            raise DataBlocked(f"{ticker}: regulatory weight cap after proposed buys")
        if projected_weight > internal_warning_weight:
            warnings.append(f"{ticker}: potential exposure above internal warning")
    return {
        "status": "PASS", "advisory_only": True, "as_of_date": state["as_of_date"],
        "nav_usd": nav, "available_cash_before_usd": state["available_cash_usd"],
        "cash_reserved_for_proposals_usd": planned_cost,
        "cash_after_reservations_usd": max(0.0, state["available_cash_usd"] - planned_cost),
        "max_position_weight": max_position_weight,
        "internal_warning_weight": internal_warning_weight,
        "execution_buffer_bps": execution_buffer_bps, "warnings": sorted(set(warnings)),
        "proposals": accepted, "proposed_order_count": len(accepted),
        "execution_authorized": False,
    }
