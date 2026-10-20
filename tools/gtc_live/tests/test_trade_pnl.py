"""Trade-aware accounting tests with invented fills, cash and WLS levels."""

from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_live.tests.test_ledger import verified_snapshot
from tools.gtc_live.trade_pnl import reconcile_filled_pnl


def example() -> tuple[dict, dict, list[dict], dict, dict]:
    before = verified_snapshot()
    b = deepcopy(before["instruments"][0])
    b.update(id="SYNTH_B UW Equity", price_local=50.0)
    before["instruments"].append(b)
    after = deepcopy(before)
    after["as_of_date"] = "2026-10-21"
    for inst in after["instruments"]:
        inst["membership_asof"] = "2026-10-21"
        inst["price_asof"] = "2026-10-21"
        inst["price_local"] += 10.0 if inst["id"] == "SYNTH UN Equity" else 5.0
    after["positions"].append({"id": "SYNTH_B UW Equity", "quantity": 1})
    after["cash_usd"] = 749.0
    fills = [
        {
            "fill_id": "F1",
            "id": "SYNTH_B UW Equity",
            "status": "FILLED",
            "side": "BUY",
            "quantity": 1,
            "execution_price_local": 50.0,
            "price_unit_multiplier": 1.0,
            "currency": "USD",
            "usd_per_unit": 1.0,
            "fee_usd": 1.0,
            "executed_at": "2026-10-21T14:35:00+00:00",
        }
    ]
    b0 = {
        "verified": True,
        "source": "synthetic WLS",
        "basis": "PRICE_RETURN",
        "as_of_date": "2026-10-20",
        "level": 1000.0,
    }
    b1 = {**b0, "as_of_date": "2026-10-21", "level": 1010.0}
    return before, after, fills, b0, b1


def test_fills_cash_and_pnl_reconcile() -> None:
    first, last, fills, b0, b1 = example()
    report = reconcile_filled_pnl(first, last, fills, b0, b1)
    assert report["nav_start_usd"] == pytest.approx(1000.0)
    assert report["nav_end_usd"] == pytest.approx(1024.0)
    assert report["pnl_usd"] == pytest.approx(24.0)
    assert report["portfolio_return"] == pytest.approx(0.024)
    assert report["active_return"] == pytest.approx(0.014)
    assert sum(row["pnl_usd"] for row in report["pnl_contributors"]) == pytest.approx(24.0)


def test_unfilled_order_is_not_a_fill() -> None:
    start, end, fills, b0, b1 = example()
    fills[0]["status"] = "OPEN"
    with pytest.raises(DataBlocked, match="FILLED"):
        reconcile_filled_pnl(start, end, fills, b0, b1)


def test_unreconciled_cash_blocks() -> None:
    start, end, fills, b0, b1 = example()
    end["cash_usd"] += 20
    with pytest.raises(DataBlocked, match="cash"):
        reconcile_filled_pnl(start, end, fills, b0, b1)


def test_unreconciled_holdings_block() -> None:
    start, end, fills, b0, b1 = example()
    end["positions"][-1]["quantity"] = 2
    with pytest.raises(DataBlocked, match="quantities"):
        reconcile_filled_pnl(start, end, fills, b0, b1)


def test_duplicate_fill_id_blocks() -> None:
    start, end, fills, b0, b1 = example()
    with pytest.raises(DataBlocked, match="unique fill_id"):
        reconcile_filled_pnl(start, end, fills + fills, b0, b1)


def test_unzoned_execution_time_blocks() -> None:
    start, end, fills, b0, b1 = example()
    fills[0]["executed_at"] = "2026-10-21T14:35:00"
    with pytest.raises(DataBlocked, match="timezone"):
        reconcile_filled_pnl(start, end, fills, b0, b1)
