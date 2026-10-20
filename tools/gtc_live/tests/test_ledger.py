"""Synthetic tests of hard-blocking reconciliation invariants."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked, reconcile


def verified_snapshot() -> dict:
    return {
        "as_of_date": "2026-10-20",
        "cash_usd": 800.0,
        "instruments": [{
            "id": "SYNTH UN Equity", "instrument_type": "EQUITY", "wls_member": True,
            "membership_asof": "2026-10-20", "price_asof": "2026-10-20",
            "currency": "USD", "price_local": 100.0, "price_unit_multiplier": 1.0,
            "usd_per_unit": 1.0,
        }],
        "positions": [{"id": "SYNTH UN Equity", "quantity": 2}],
        "pending_orders": [],
    }


def test_nav_cash_and_position_weights() -> None:
    state = reconcile(verified_snapshot())
    assert state["nav_usd"] == pytest.approx(1000.0)
    assert state["positions"][0]["weight"] == pytest.approx(0.2)
    assert state["available_cash_usd"] == pytest.approx(800.0)


def test_pending_buy_does_not_count_as_executed_holdings() -> None:
    raw = verified_snapshot()
    raw["pending_orders"] = [
        {"order_id": "A", "status": "OPEN", "side": "BUY",
         "id": "SYNTH UN Equity", "remaining_quantity": 1, "limit_price_local": 101}
    ]
    state = reconcile(raw)
    assert state["pending_reserved_usd"] == pytest.approx(101.0)
    assert state["available_cash_usd"] == pytest.approx(699.0)
    assert state["positions"][0]["quantity"] == 2


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(cash_usd=-1),
    lambda s: s["instruments"][0].update(price_asof="2026-10-01"),
    lambda s: s["instruments"][0].update(wls_member=False),
    lambda s: s["instruments"][0].update(instrument_type="ETF"),
    lambda s: s["instruments"][0].update(usd_per_unit=1.1),
    lambda s: s["positions"].append({"id": "SYNTH UN Equity", "quantity": 3}),
    lambda s: s["pending_orders"].append({
        "order_id": "A", "status": "OPEN", "side": "SELL",
        "id": "SYNTH UN Equity", "remaining_quantity": 3}),
    lambda s: s["pending_orders"].append({
        "order_id": "A", "status": "OPEN", "side": "BUY",
        "id": "SYNTH UN Equity", "remaining_quantity": 9,
        "limit_price_local": 100}),
    lambda s: s.update(as_of_date="2026-10-19"),
])
def test_invalid_or_unknown_state_blocks(mutation) -> None:
    source = deepcopy(verified_snapshot())
    mutation(source)
    with pytest.raises(DataBlocked):
        reconcile(source)


def test_fx_conversion_respects_major_currency_and_unit() -> None:
    state = verified_snapshot()
    state["instruments"][0].update(currency="GBP", price_local=10.0,
                                   price_unit_multiplier=0.01, usd_per_unit=1.2,
                                   fx_asof="2026-10-20")
    result = reconcile(state)
    assert result["positions"][0]["mark_usd"] == pytest.approx(0.12)
