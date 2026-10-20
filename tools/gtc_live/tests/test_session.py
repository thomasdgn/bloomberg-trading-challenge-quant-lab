"""All-or-nothing daily session tests."""
from __future__ import annotations

import pytest

from tools.gtc_live.freshness import REQUIRED_SOURCES
from tools.gtc_live.ledger import DataBlocked
from tools.gtc_live.session import assess_session
from tools.gtc_live.tests.test_ledger import verified_snapshot


def input_payload() -> dict:
    return {
        "snapshot": verified_snapshot(), "proposals": [],
        "feed_manifest": {
            "as_of_date": "2026-10-20",
            "sources": {
                name: {"verified": True, "observed_date": "2026-10-20",
                       "provenance": f"operator-confirmed-{name}"}
                for name in REQUIRED_SOURCES
            },
        },
    }


def test_session_pass_does_not_authorize_execution() -> None:
    report = assess_session(input_payload())
    assert report["status"] == "PASS"
    assert report["execution_authorized"] is False


def test_stale_wls_blocks_even_with_good_trades() -> None:
    payload = input_payload()
    payload["feed_manifest"]["sources"]["wls_benchmark"]["observed_date"] = "2026-10-07"
    with pytest.raises(DataBlocked, match="wls_benchmark"):
        assess_session(payload)


def test_mismatched_snapshot_and_feed_dates_block() -> None:
    payload = input_payload()
    payload["feed_manifest"]["as_of_date"] = "2026-10-19"
    with pytest.raises(DataBlocked, match="mismatch"):
        assess_session(payload)
