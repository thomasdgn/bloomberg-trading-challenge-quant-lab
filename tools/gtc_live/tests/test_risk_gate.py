"""Regression tests for conservative proposed-order preflight."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_live.risk_gate import check_trade_plan
from tools.gtc_live.tests.test_ledger import verified_snapshot


def two_assets() -> dict:
    state = verified_snapshot()
    extra = deepcopy(state["instruments"][0])
    extra.update(id="SYNTH_B UW Equity", price_local=50.0)
    state["instruments"].append(extra)
    return state


def test_funded_new_purchase_passes_but_never_authorizes_execution() -> None:
    state = two_assets()
    output = check_trade_plan(state, [
        {"client_id": "intent-1", "id": "SYNTH_B UW Equity",
         "side": "BUY", "quantity": 2, "limit_price_local": 51.0}
    ])
    assert output["status"] == "PASS"
    assert output["execution_authorized"] is False
    assert output["cash_reserved_for_proposals_usd"] == pytest.approx(102.204)


def test_buy_above_cap_blocks() -> None:
    with pytest.raises(DataBlocked, match="cap"):
        check_trade_plan(two_assets(), [
            {"client_id": "intent-1", "id": "SYNTH UN Equity",
             "side": "BUY", "quantity": 1}
        ])


def test_pending_buy_cannot_be_placed_twice() -> None:
    state = two_assets()
    state["pending_orders"] = [
        {"order_id": "live-9", "status": "OPEN", "id": "SYNTH_B UW Equity",
         "side": "BUY", "remaining_quantity": 1, "limit_price_local": 50}
    ]
    with pytest.raises(DataBlocked, match="pending"):
        check_trade_plan(state, [
            {"client_id": "new-9", "id": "SYNTH_B UW Equity",
             "side": "BUY", "quantity": 1}
        ])


def test_sell_cannot_consume_shares_already_queued_for_sale() -> None:
    state = two_assets()
    state["pending_orders"] = [
        {"order_id": "sell-live", "status": "PARTIAL", "id": "SYNTH UN Equity",
         "side": "SELL", "remaining_quantity": 1}
    ]
    with pytest.raises(DataBlocked, match="exceed"):
        check_trade_plan(state, [
            {"client_id": "sell-again", "id": "SYNTH UN Equity",
             "side": "SELL", "quantity": 2}
        ])


def test_missing_member_never_passes() -> None:
    with pytest.raises(DataBlocked, match="missing verified WLS"):
        check_trade_plan(two_assets(), [
            {"client_id": "unknown", "id": "NOT WLS Equity",
             "side": "BUY", "quantity": 1}
        ])


def test_negative_or_nan_order_size_fails_closed() -> None:
    for quantity in (-1, float("nan")):
        with pytest.raises(DataBlocked):
            check_trade_plan(two_assets(), [
                {"client_id": "bad", "id": "SYNTH_B UW Equity",
                 "side": "BUY", "quantity": quantity}
            ])
