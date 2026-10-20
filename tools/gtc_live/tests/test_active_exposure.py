"""Verified whole-index active exposure invariants."""
from __future__ import annotations

import pytest

from tools.gtc_live.active_exposure import compare_active_exposures
from tools.gtc_live.ledger import DataBlocked
from tools.gtc_live.tests.test_ledger import verified_snapshot


def index() -> dict:
    return {
        "verified_full_universe": True, "source": "SYNTHETIC WLS EXAMPLE",
        "as_of_date": "2026-10-20", "expected_constituent_count": 2,
        "constituents": [
            {"id": "SYNTH UN Equity", "weight": 0.6,
             "sector": "Technology", "country": "US", "currency": "USD"},
            {"id": "SYNTH_B UW Equity", "weight": 0.4,
             "sector": "Financials", "country": "US", "currency": "USD"},
        ],
    }


def test_active_weight_and_cash_are_consistent() -> None:
    result = compare_active_exposures(verified_snapshot(), index())
    assert result["active_share"] == pytest.approx(0.8)
    assert result["active_weight_total"] == pytest.approx(0.0)
    assert result["group_exposures"]["sector"]["Technology"]["active_weight"] == pytest.approx(
        -0.4
    )
    assert result["group_exposures"]["sector"]["USD_CASH"]["active_weight"] == pytest.approx(
        0.8
    )


def test_partial_weight_file_blocks() -> None:
    broken = index()
    broken["constituents"][1]["weight"] = 0.1
    with pytest.raises(DataBlocked, match="sum"):
        compare_active_exposures(verified_snapshot(), broken)


def test_missing_metadata_blocks() -> None:
    broken = index()
    del broken["constituents"][1]["sector"]
    with pytest.raises(DataBlocked, match="sector"):
        compare_active_exposures(verified_snapshot(), broken)


def test_unverified_constituents_block() -> None:
    broken = index()
    broken["verified_full_universe"] = False
    with pytest.raises(DataBlocked, match="verified complete"):
        compare_active_exposures(verified_snapshot(), broken)


def test_snapshot_date_must_be_supported() -> None:
    broken = index()
    broken["as_of_date"] = "2026-10-07"
    with pytest.raises(DataBlocked, match="stale"):
        compare_active_exposures(verified_snapshot(), broken)
