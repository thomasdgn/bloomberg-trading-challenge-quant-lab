"""Strict input checks: verified, contemporary USD price-return panels only."""

from __future__ import annotations

from datetime import date
from math import isclose, isfinite
from typing import Any

from tools.gtc_live.ledger import DataBlocked, age_days, reconcile

END_DATE = date(2026, 11, 13)
CASH = "USD_CASH"


def _number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        raise DataBlocked(f"{label}: number required, not boolean")
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise DataBlocked(f"{label}: numeric value required") from exc
    if not isfinite(number) or number < minimum:
        raise DataBlocked(f"{label}: invalid or non-finite value")
    return number


def validate_weights(weights: Any, allowed: set[str], label: str) -> dict[str, float]:
    if not isinstance(weights, dict) or not weights:
        raise DataBlocked(f"{label}: explicit target weight mapping required")
    if CASH not in weights:
        raise DataBlocked(f"{label}: explicit USD_CASH target required")
    if set(weights) - allowed - {CASH}:
        raise DataBlocked(f"{label}: unverified, unsupported or ineligible asset")
    mapped = {str(k): _number(v, f"{label}:{k}") for k, v in weights.items()}
    for ticker, weight in mapped.items():
        if ticker != CASH and weight > 0.20 + 1e-10:
            raise DataBlocked(f"{label}:{ticker}: exceeds WLS challenge 20% cap")
    if not isclose(sum(mapped.values()), 1.0, abs_tol=1e-9):
        raise DataBlocked(f"{label}: weights, including cash, must sum to one")
    return {ticker: mapped.get(ticker, 0.0) for ticker in sorted(allowed | {CASH})}


def prepare(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DataBlocked("simulation input must be a JSON object")
    state = reconcile(payload.get("snapshot"))
    as_of = date.fromisoformat(state["as_of_date"])
    if as_of >= END_DATE:
        raise DataBlocked("decision must precede challenge end 2026-11-13")
    if state["pending_orders"]:
        raise DataBlocked("pending/partial orders must settle before simulation")
    if payload.get("decision_cutoff") != state["as_of_date"]:
        raise DataBlocked("decision_cutoff must match verified portfolio valuation date")
    instruments = set(state["instruments"])
    if CASH in instruments:
        raise DataBlocked("USD_CASH is reserved for cash")
    held = {row["id"]: row["weight"] for row in state["positions"]}
    hold = validate_weights(
        {**held, CASH: state["cash_usd"] / state["nav_usd"]},
        instruments,
        "HOLD",
    )
    target = validate_weights(payload.get("rebalance_weights"), instruments, "REBALANCE")
    scale = _number(payload.get("defensive_equity_scale"), "defensive_equity_scale")
    if not 0 <= scale < 1:
        raise DataBlocked("defensive_equity_scale must be >= 0 and < 1")
    defensive = {k: hold[k] * scale for k in instruments}
    defensive[CASH] = 1.0 - sum(defensive.values())
    defensive = validate_weights(defensive, instruments, "DEFENSIVE")

    costs = _number(payload.get("assumed_execution_cost_bps"), "assumed_execution_cost_bps")
    if costs > 300:
        raise DataBlocked("cost assumption >300bps requires separate review")
    paths = payload.get("bootstrap_paths", 1000)
    seed = payload.get("seed", 20261021)
    block = payload.get("block_size_sessions", 5)
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (paths, seed, block)):
        raise DataBlocked("bootstrap_paths, seed and block_size_sessions must be integers")
    if not (200 <= paths <= 5000) or not (1 <= block <= 20):
        raise DataBlocked("paths 200..5000 and block size 1..20 required")

    calendar = payload.get("verified_exchange_sessions")
    if not isinstance(calendar, list) or not calendar:
        raise DataBlocked("verified_exchange_sessions missing")
    try:
        session_dates = [date.fromisoformat(s) for s in calendar]
    except (TypeError, ValueError) as exc:
        raise DataBlocked("verified_exchange_sessions must be ISO dates") from exc
    if session_dates != sorted(set(session_dates)):
        raise DataBlocked("exchange session list must be strictly sorted, unique")
    if session_dates[0] > as_of or session_dates[-1] < END_DATE:
        raise DataBlocked("exchange calendar does not cover full requested horizon")
    if END_DATE not in session_dates or any(d.weekday() >= 5 for d in session_dates):
        raise DataBlocked("verified exchange calendar incomplete or includes weekend")
    future = [d for d in session_dates if as_of < d <= END_DATE]
    if not (1 <= len(future) <= 28):
        raise DataBlocked("unexpected number of remaining trading sessions")

    verification = payload.get("data_verification")
    if not isinstance(verification, dict):
        raise DataBlocked("data_verification manifest missing")
    if verification.get("verified_by_operator") is not True:
        raise DataBlocked("source data must be explicitly operator-verified")
    if verification.get("basis") != "SPLIT_ADJUSTED_PRICE_RETURN_USD":
        raise DataBlocked("returns must be split-adjusted price returns in USD")
    if verification.get("benchmark_id") != "WLS Index":
        raise DataBlocked("only actual WLS Index is permitted; no proxy")
    if not str(verification.get("source", "")).strip():
        raise DataBlocked("source provenance required")
    if verification.get("selection_policy") != "AS_OF_VERIFIED":
        raise DataBlocked("verify WLS membership and no future candidate selection")
    age_days(verification.get("validated_at"), as_of, "validation", 7)

    raw_history = payload.get("history")
    if not isinstance(raw_history, list) or len(raw_history) < 80:
        raise DataBlocked("at least 80 aligned historical USD daily rows required")
    history = []
    last_date = None
    for row in raw_history:
        if not isinstance(row, dict):
            raise DataBlocked("each return row must be an object")
        try:
            day = date.fromisoformat(row["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DataBlocked("invalid historical observation date") from exc
        if day >= as_of or (last_date is not None and day <= last_date):
            raise DataBlocked("history must be strictly ordered and pre-decision")
        if day.weekday() >= 5:
            raise DataBlocked("historical returns must use verified exchange sessions")
        last_date = day
        wls = _number(row.get("wls"), f"{day} WLS daily return", minimum=-1)
        if wls <= -1:
            raise DataBlocked("WLS daily index cannot reach -100%")
        returns = row.get("returns")
        if not isinstance(returns, dict) or set(returns) != instruments:
            raise DataBlocked(f"{day}: every eligible asset needs a joint USD return")
        formatted = {}
        for ticker, value in returns.items():
            value = _number(value, f"{day}:{ticker}", minimum=-1)
            if value <= -1:
                raise DataBlocked(f"{day}:{ticker}: -100% return unsupported")
            formatted[ticker] = value
        history.append({"date": str(day), "wls": wls, "returns": formatted})
    if (as_of - last_date).days > 7:
        raise DataBlocked("historical WLS and stock panel ends more than 7 days before decision")
    if block > len(history):
        raise DataBlocked("bootstrap block longer than available history")

    return {
        "as_of_date": str(as_of),
        "challenge_end": str(END_DATE),
        "horizon_sessions": len(future),
        "future_sessions": [str(day) for day in future],
        "paths": paths,
        "seed": seed,
        "block": block,
        "cost_bps": costs,
        "source": verification["source"],
        "history": history,
        "holdings": hold,
        "scenarios": {
            "HOLD": hold,
            "REBALANCE": target,
            "DEFENSIVE": defensive,
        },
        "instruments": sorted(instruments),
        "defensive_equity_scale": scale,
    }
