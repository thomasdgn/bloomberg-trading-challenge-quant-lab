"""Strict, read-only reconciliation of *executed* holdings and open orders.

All prices and conversions are explicitly dated. Never infer execution from a submitted order.
No direct interaction with Bloomberg or TMSG. Values are as supplied by the operator.
"""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Any


class DataBlocked(ValueError):
    """Missing or inconsistent input must block rather than guess."""


def positive(value: Any, label: str, *, zero_ok: bool = False) -> float:
    if isinstance(value, bool):
        raise DataBlocked(f"{label}: boolean is not a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DataBlocked(f"{label}: valid number required") from exc
    if not isfinite(result) or result < 0 or (not zero_ok and result == 0):
        raise DataBlocked(f"{label}: invalid non-finite/negative/zero value")
    return result


def age_days(value: Any, as_of: date, label: str, max_age: int) -> int:
    try:
        observed = date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise DataBlocked(f"{label}: ISO date required") from exc
    age = (as_of - observed).days
    if age < 0 or age > max_age:
        raise DataBlocked(f"{label}: future or stale observation ({age} days)")
    return age


def _asof(snapshot: dict[str, Any]) -> date:
    try:
        return date.fromisoformat(str(snapshot["as_of_date"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise DataBlocked("as_of_date: ISO date required") from exc


def reconcile(snapshot: dict[str, Any], *, max_quote_age_days: int = 4) -> dict[str, Any]:
    """Reconcile marked NAV, buying power, pending orders and held quantities.

    Schema: as_of_date, cash_usd, instruments[], positions[], pending_orders[].
    Instrument marks use explicit local price × local unit multiplier × USD/local FX.
    Open and partially filled orders contain *remaining_quantity only*.
    """
    if not isinstance(snapshot, dict) or max_quote_age_days < 0:
        raise DataBlocked("Invalid snapshot or quote age configuration")
    as_of = _asof(snapshot)
    cash = positive(snapshot.get("cash_usd"), "cash_usd", zero_ok=True)
    instruments = {}
    raw_instruments = snapshot.get("instruments")
    if not isinstance(raw_instruments, list) or not raw_instruments:
        raise DataBlocked("instruments: nonempty verified snapshot required")
    for raw in raw_instruments:
        if not isinstance(raw, dict):
            raise DataBlocked("instruments: object expected")
        ticker = str(raw.get("id", "")).strip()
        if not ticker or ticker in instruments:
            raise DataBlocked("instruments: blank or duplicate id")
        if raw.get("wls_member") is not True or raw.get("instrument_type") != "EQUITY":
            raise DataBlocked(f"{ticker}: not verified as eligible WLS EQUITY")
        age_days(raw.get("membership_asof"), as_of, f"{ticker} membership", 7)
        age_days(raw.get("price_asof"), as_of, f"{ticker} price", max_quote_age_days)
        currency = str(raw.get("currency", "")).upper()
        if len(currency) != 3 or not currency.isalpha():
            raise DataBlocked(f"{ticker}: three-letter currency required")
        price = positive(raw.get("price_local"), f"{ticker} price_local")
        multiplier = positive(raw.get("price_unit_multiplier"), f"{ticker} price_unit_multiplier")
        if currency == "USD":
            fx = positive(raw.get("usd_per_unit"), f"{ticker} USD FX")
            if abs(fx - 1) > 1e-10:
                raise DataBlocked(f"{ticker}: USD FX must be 1")
        else:
            age_days(raw.get("fx_asof"), as_of, f"{ticker} FX", max_quote_age_days)
            fx = positive(raw.get("usd_per_unit"), f"{ticker} USD FX")
        mark = price * multiplier * fx
        if not isfinite(mark) or mark <= 0:
            raise DataBlocked(f"{ticker}: invalid converted price")
        instruments[ticker] = {
            "id": ticker,
            "price_usd": mark,
            "currency": currency,
            "price_asof": raw["price_asof"],
            "fx_asof": raw.get("fx_asof"),
        }
    quantities = {}
    positions = snapshot.get("positions")
    if not isinstance(positions, list):
        raise DataBlocked("positions: explicit list required, even when empty")
    for position in positions:
        if not isinstance(position, dict):
            raise DataBlocked("positions: object expected")
        ticker = str(position.get("id", "")).strip()
        if ticker not in instruments or ticker in quantities:
            raise DataBlocked(f"{ticker}: unknown or duplicate executed position")
        qty = positive(position.get("quantity"), f"{ticker} executed quantity")
        quantities[ticker] = qty
    nav = cash + sum(qty * instruments[t]["price_usd"] for t, qty in quantities.items())
    if not isfinite(nav) or nav <= 0:
        raise DataBlocked("NAV must be positive")
    orders = snapshot.get("pending_orders")
    if not isinstance(orders, list):
        raise DataBlocked("pending_orders: explicit list required")
    seen_orders = set()
    reserved = 0.0
    pending_buy_qty = {}
    pending_sell_qty = {}
    pending_rows = []
    for order in orders:
        if not isinstance(order, dict):
            raise DataBlocked("pending_orders: object expected")
        oid = str(order.get("order_id", "")).strip()
        if not oid or oid in seen_orders:
            raise DataBlocked("pending_orders: missing or duplicate order_id")
        seen_orders.add(oid)
        status = str(order.get("status", "")).upper()
        if status not in {"OPEN", "PARTIAL"}:
            raise DataBlocked(f"{oid}: pending_orders accepts OPEN/PARTIAL only")
        ticker = str(order.get("id", "")).strip()
        side = str(order.get("side", "")).upper()
        if ticker not in instruments or side not in {"BUY", "SELL"}:
            raise DataBlocked(f"{oid}: invalid instrument or side")
        qty = positive(order.get("remaining_quantity"), f"{oid} remaining_quantity")
        if side == "BUY":
            limit = positive(order.get("limit_price_local"), f"{oid} limit_price_local")
            raw = next(x for x in raw_instruments if x["id"] == ticker)
            price_limit_usd = (
                limit * float(raw["price_unit_multiplier"]) * float(raw["usd_per_unit"])
            )
            # Reserve the WORST of latest mark and submitted limit; fills are not assumed.
            worst = max(price_limit_usd, instruments[ticker]["price_usd"])
            reserved += qty * worst
            pending_buy_qty[ticker] = pending_buy_qty.get(ticker, 0.0) + qty
        else:
            price_limit_usd = None
            pending_sell_qty[ticker] = pending_sell_qty.get(ticker, 0.0) + qty
        pending_rows.append(
            {
                "order_id": oid,
                "id": ticker,
                "side": side,
                "status": status,
                "remaining_quantity": qty,
                "limit_price_usd": price_limit_usd,
            }
        )
    for ticker, qty in pending_sell_qty.items():
        if qty > quantities.get(ticker, 0.0) + 1e-9:
            raise DataBlocked(f"{ticker}: pending sells exceed executed holdings")
    if reserved > cash + max(1e-8, nav * 1e-9):
        raise DataBlocked("Pending BUY orders exceed confirmed USD cash")
    return {
        "as_of_date": str(as_of),
        "cash_usd": cash,
        "nav_usd": nav,
        "available_cash_usd": max(0.0, cash - reserved),
        "pending_reserved_usd": reserved,
        "positions": [
            {
                "id": t,
                "quantity": qty,
                "mark_usd": instruments[t]["price_usd"],
                "market_value_usd": qty * instruments[t]["price_usd"],
                "weight": qty * instruments[t]["price_usd"] / nav,
            }
            for t, qty in sorted(quantities.items())
        ],
        "pending_orders": pending_rows,
        "pending_buy_quantity": pending_buy_qty,
        "pending_sell_quantity": pending_sell_qty,
        "instruments": instruments,
    }
