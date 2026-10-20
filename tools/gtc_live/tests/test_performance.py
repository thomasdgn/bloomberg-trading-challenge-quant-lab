"""Daily active P&L attribution tests on fabricated portfolio marks."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_live.performance import daily_relative_pnl
from tools.gtc_live.tests.test_ledger import verified_snapshot


def two_dates() -> tuple[dict, dict, dict, dict]:
    first = verified_snapshot()
    last = deepcopy(first)
    last["as_of_date"] = "2026-10-21"
    last["instruments"][0].update(price_local=110.0, price_asof="2026-10-21",
                                   membership_asof="2026-10-21")
    b0 = {"as_of_date": "2026-10-20", "verified": True, "basis": "PRICE_RETURN",
          "level": 1000.0, "source": "verified-WLS-example"}
    b1 = {**b0, "as_of_date": "2026-10-21", "level": 1010.0}
    return first, last, b0, b1


def test_active_pnl_equals_attribution_sum() -> None:
    before, after, b0, b1 = two_dates()
    result = daily_relative_pnl(before, after, b0, b1)
    assert result["portfolio_return"] == pytest.approx(0.02)
    assert result["benchmark_return"] == pytest.approx(0.01)
    assert result["active_return"] == pytest.approx(0.01)
    assert result["cash_active_contribution"] == pytest.approx(-0.008)
    assert result["contributions"][0]["active_contribution"] == pytest.approx(0.018)


def test_unverified_benchmark_blocks() -> None:
    before, after, b0, b1 = two_dates()
    b1["verified"] = False
    with pytest.raises(DataBlocked, match="benchmark"):
        daily_relative_pnl(before, after, b0, b1)


def test_changes_in_holdings_or_cash_block_false_no_trade_pnl() -> None:
    before, after, b0, b1 = two_dates()
    after["positions"][0]["quantity"] += 1
    with pytest.raises(DataBlocked, match="holdings changed"):
        daily_relative_pnl(before, after, b0, b1)
    after["positions"][0]["quantity"] -= 1
    after["cash_usd"] += 5
    with pytest.raises(DataBlocked, match="cash changed"):
        daily_relative_pnl(before, after, b0, b1)


def test_pending_order_blocks_simple_attribution() -> None:
    before, after, b0, b1 = two_dates()
    after["pending_orders"] = [{
        "order_id": "pending", "status": "OPEN", "side": "SELL",
        "id": "SYNTH UN Equity", "remaining_quantity": 1,
    }]
    with pytest.raises(DataBlocked, match="pending orders"):
        daily_relative_pnl(before, after, b0, b1)
