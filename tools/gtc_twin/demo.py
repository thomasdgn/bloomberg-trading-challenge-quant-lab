"""Make a clearly fictional end-to-end Digital Twin demonstration JSON.

No real securities, Bloomberg subscription, rankings or empirical alpha used.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.__main__ import _under_output_root


def build_demo() -> dict:
    today = date(2026, 10, 21)
    ids = ["SIMULATED_ALPHA Equity", "SIMULATED_BETA Equity"]
    stocks = [{
        "id": name, "instrument_type": "EQUITY", "wls_member": True,
        "membership_asof": str(today), "price_asof": str(today),
        "price_local": 100.0, "currency": "USD",
        "price_unit_multiplier": 1.0, "usd_per_unit": 1.0,
    } for name in ids]
    past_days = []
    day = today - timedelta(days=1)
    while len(past_days) < 120:
        if day.weekday() < 5:
            past_days.append(day)
        day -= timedelta(days=1)
    past_days.reverse()
    history = [{
        "date": str(day),
        "wls": ((i % 11) - 5) * 0.0006,
        "returns": {
            ids[0]: ((i % 13) - 6) * 0.0009 + 0.0004,
            ids[1]: ((i % 7) - 3) * 0.0008 - 0.0002,
        },
    } for i, day in enumerate(past_days)]
    sessions = []
    day = today
    while day <= date(2026, 11, 13):
        if day.weekday() < 5:
            sessions.append(str(day))
        day += timedelta(days=1)
    return {
        "decision_cutoff": str(today),
        "snapshot": {
            "as_of_date": str(today), "cash_usd": 600,
            "instruments": stocks,
            "positions": [{"id": name, "quantity": 2} for name in ids],
            "pending_orders": [],
        },
        "rebalance_weights": {ids[0]: 0.10, ids[1]: 0.20, "USD_CASH": 0.70},
        "defensive_equity_scale": 0.5,
        "assumed_execution_cost_bps": 15.0,
        "bootstrap_paths": 400, "seed": 20261021,
        "block_size_sessions": 5,
        "verified_exchange_sessions": sessions,
        "data_verification": {
            "verified_by_operator": True,
            "basis": "SPLIT_ADJUSTED_PRICE_RETURN_USD",
            "benchmark_id": "WLS Index",
            "selection_policy": "AS_OF_VERIFIED",
            "validated_at": str(today),
            "source": "SYNTHETIC DEMONSTRATION — NOT REAL WLS DATA",
        },
        "history": history,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fictional Twin input data")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        destination = _under_output_root(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as handle:
            json.dump(build_demo(), handle, indent=2)
            handle.write("\n")
    except (DataBlocked, OSError) as exc:
        parser.error(str(exc))
    print(f"SYNTHETIC ONLY — example created at {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
