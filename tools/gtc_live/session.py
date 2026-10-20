"""Single fail-closed session preflight: feed gate + actual holdings + orders."""

from __future__ import annotations

from typing import Any

from tools.gtc_live.freshness import audit_freshness
from tools.gtc_live.ledger import DataBlocked
from tools.gtc_live.risk_gate import check_trade_plan


def assess_session(payload: dict[str, Any]) -> dict[str, Any]:
    """Both gates must PASS for a candidate plan to be described as reviewed.

    This is only a deterministic data/constraints check. It cannot verify the
    honesty of operator-supplied source attestations or authorize execution.
    """
    if not isinstance(payload, dict):
        raise DataBlocked("session payload object required")
    feed = payload.get("feed_manifest")
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        raise DataBlocked("snapshot object required")
    if not isinstance(feed, dict):
        raise DataBlocked("feed_manifest object required")
    if feed.get("as_of_date") != snapshot.get("as_of_date"):
        raise DataBlocked("portfolio and feed as_of_date mismatch")
    fresh = audit_freshness(feed)
    proposed = payload.get("proposals")
    if not isinstance(proposed, list):
        raise DataBlocked("proposals list required (use [] for a dry-run)")
    pretrade = check_trade_plan(snapshot, proposed)
    return {
        "status": "PASS",
        "as_of_date": pretrade["as_of_date"],
        "advisory_only": True,
        "execution_authorized": False,
        "feed": fresh,
        "pretrade": pretrade,
        "limits": [
            "human-verified source truth and Bloomberg/TMSG permissions still required",
            "no price move, gap, FX change or order execution can be guaranteed",
            "pending sells never fund proposed buys",
        ],
    }
