"""Purely synthetic GTC Digital Twin fixtures; no real Bloomberg holdings."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


@pytest.fixture
def example_payload() -> dict:
    as_of = date(2026, 10, 21)
    instruments = [
        {
            "id": ticker, "instrument_type": "EQUITY", "wls_member": True,
            "membership_asof": str(as_of), "price_asof": str(as_of),
            "currency": "USD", "price_local": 100,
            "price_unit_multiplier": 1, "usd_per_unit": 1,
        }
        for ticker in ("SYNTH_A UN Equity", "SYNTH_B UN Equity")
    ]
    older_dates = []
    current = as_of - timedelta(days=1)
    while len(older_dates) < 120:
        if current.weekday() < 5:
            older_dates.append(current)
        current -= timedelta(days=1)
    older_dates.reverse()
    history = [
        {
            "date": str(day),
            "wls": 0.0002 + (i % 8 - 4) * 0.0003,
            "returns": {
                "SYNTH_A UN Equity": 0.0004 + (i % 9 - 4) * 0.0008,
                "SYNTH_B UN Equity": -0.0002 - (i % 9 - 4) * 0.0005,
            },
        }
        for i, day in enumerate(older_dates)
    ]
    days = []
    current = as_of
    while current <= date(2026, 11, 13):
        if current.weekday() < 5:
            days.append(str(current))
        current += timedelta(days=1)
    return {
        "decision_cutoff": str(as_of),
        "snapshot": {
            "as_of_date": str(as_of), "cash_usd": 600,
            "instruments": instruments,
            "positions": [
                {"id": "SYNTH_A UN Equity", "quantity": 2},
                {"id": "SYNTH_B UN Equity", "quantity": 2},
            ],
            "pending_orders": [],
        },
        "rebalance_weights": {
            "SYNTH_A UN Equity": 0.10,
            "SYNTH_B UN Equity": 0.20,
            "USD_CASH": 0.70,
        },
        "defensive_equity_scale": 0.50,
        "assumed_execution_cost_bps": 15.0,
        "bootstrap_paths": 200,
        "seed": 20261021,
        "block_size_sessions": 5,
        "verified_exchange_sessions": days,
        "data_verification": {
            "verified_by_operator": True,
            "basis": "SPLIT_ADJUSTED_PRICE_RETURN_USD",
            "benchmark_id": "WLS Index",
            "selection_policy": "AS_OF_VERIFIED",
            "validated_at": str(as_of),
            "source": "synthetic unit tests only",
        },
        "history": history,
    }
