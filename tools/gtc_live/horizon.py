"""Competition horizon uses a caller-supplied *verified exchange calendar*."""

from __future__ import annotations

from datetime import date
from typing import Any

from tools.gtc_live.ledger import DataBlocked

END_DATE = date(2026, 11, 13)


def remaining_horizon(as_of_date: str, exchange_sessions: list[str]) -> dict[str, Any]:
    """Count remaining sessions to Nov 13; never silently assume 5 sessions/week."""
    try:
        today = date.fromisoformat(as_of_date)
        sessions = [date.fromisoformat(day) for day in exchange_sessions]
    except (TypeError, ValueError) as exc:
        raise DataBlocked("ISO dates and a verified session calendar required") from exc
    if today > END_DATE:
        raise DataBlocked("challenge already ended")
    if sessions != sorted(set(sessions)) or not sessions:
        raise DataBlocked("session calendar must be nonempty, sorted and unique")
    if sessions[0] > today or sessions[-1] < END_DATE:
        raise DataBlocked("session calendar does not cover decision and end dates")
    if any(d.weekday() >= 5 for d in sessions):
        raise DataBlocked("exchange session list contains a weekend")
    remaining = [d for d in sessions if today < d <= END_DATE]
    return {
        "as_of_date": str(today),
        "challenge_end": str(END_DATE),
        "remaining_exchange_sessions": len(remaining),
        "remaining_calendar_days": (END_DATE - today).days,
        "remaining_sessions": [str(d) for d in remaining],
        "annualization_or_return_forecast": None,
        "note": "Schedule only; do not reuse a 4-week alpha as a shorter-horizon forecast.",
    }
