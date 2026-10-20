"""Synthetic horizon and stress tests; scenarios are not probability forecasts."""

from __future__ import annotations

import pytest

from tools.gtc_live.horizon import remaining_horizon
from tools.gtc_live.ledger import DataBlocked
from tools.gtc_live.scenarios import stress_portfolio
from tools.gtc_live.tests.test_ledger import verified_snapshot


def test_horizon_from_exchange_calendar() -> None:
    # 19 Oct through 13 Nov on verified synthetic weekday calendar.
    from datetime import date, timedelta

    days = [date(2026, 10, 19) + timedelta(days=i) for i in range(26)]
    sessions = [str(day) for day in days if day.weekday() < 5]
    result = remaining_horizon("2026-10-20", sessions)
    assert result["challenge_end"] == "2026-11-13"
    assert result["remaining_exchange_sessions"] == 18
    assert result["annualization_or_return_forecast"] is None


def test_missing_challenge_end_session_is_rejected() -> None:
    with pytest.raises(DataBlocked, match="does not cover"):
        remaining_horizon("2026-10-20", ["2026-10-20", "2026-10-21"])


def test_stress_mechanics_are_explicit() -> None:
    result = stress_portfolio(verified_snapshot(), {"DOWN_25": {"SYNTH UN Equity": -0.25}})
    assert result["scenarios"][0]["portfolio_pnl_usd"] == pytest.approx(-50)
    assert result["scenarios"][0]["portfolio_return"] == pytest.approx(-0.05)


def test_missing_shock_fails_closed() -> None:
    with pytest.raises(DataBlocked, match="every held"):
        stress_portfolio(verified_snapshot(), {"INCOMPLETE": {}})
