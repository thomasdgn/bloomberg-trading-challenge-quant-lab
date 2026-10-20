"""Append-only locally verified decision journal with SHA-256 hash chaining.

This provides tamper evidence against accidental edits, NOT non-repudiation:
a malicious party can rewrite the complete file and its hashes. Retain an
independent exported digest if stronger external auditability is needed.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.engine import fingerprint
from tools.gtc_twin.schema import END_DATE

ZERO = "0" * 64


def _path_inside(journal: str | Path, root: str | Path) -> Path:
    root = Path(root).resolve()
    resolved = Path(journal).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise DataBlocked("journal must be within ignored outputs/gtc_twin")
    if resolved.suffix != ".jsonl" or resolved.is_symlink():
        raise DataBlocked("journal must be a local .jsonl file, not a symlink")
    return resolved


def verify_journal(
    journal: str | Path, *, root: str | Path = "outputs/gtc_twin"
) -> dict[str, Any]:
    path = _path_inside(journal, root)
    if not path.is_file():
        return {"status": "PASS", "events": 0, "last_sha256": ZERO,
                "decisions": 0, "checkpoints": 0, "final_outcomes": 0}
    expected = ZERO
    seen_ids: dict[str, str] = {}
    checkpoints = set()
    final_outcomes = set()
    counts = {"DECISION": 0, "CHECKPOINT": 0, "FINAL_OUTCOME": 0}
    with path.open(encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DataBlocked(f"journal line {line_num}: malformed JSON") from exc
            if not isinstance(record, dict):
                raise DataBlocked(f"journal line {line_num}: object expected")
            signature = record.get("sha256")
            body = {k: v for k, v in record.items() if k != "sha256"}
            if (
                record.get("seq") != line_num
                or record.get("prev_sha256") != expected
                or fingerprint(body) != signature
            ):
                raise DataBlocked(f"journal line {line_num}: broken hash chain")
            kind = record.get("kind")
            if kind not in counts or not isinstance(record.get("data"), dict):
                raise DataBlocked(f"journal line {line_num}: unknown event")
            data = record["data"]
            run = data.get("run_id")
            if not isinstance(run, str) or not run:
                raise DataBlocked("journal: every event must identify a run")
            if kind == "DECISION":
                if run in seen_ids:
                    raise DataBlocked("duplicate decision run_id")
                seen_ids[run] = str(data.get("decision_date", ""))
            elif run not in seen_ids:
                raise DataBlocked("outcome/checkpoint without earlier decision")
            if kind == "CHECKPOINT":
                key = (run, data.get("observation_date"))
                if key in checkpoints:
                    raise DataBlocked("duplicate checkpoint")
                checkpoints.add(key)
            elif kind == "FINAL_OUTCOME":
                if run in final_outcomes:
                    raise DataBlocked("duplicate final outcome")
                final_outcomes.add(run)
            counts[kind] += 1
            expected = signature
    return {"status": "PASS", "events": sum(counts.values()),
            "last_sha256": expected, "decisions": counts["DECISION"],
            "checkpoints": counts["CHECKPOINT"],
            "final_outcomes": counts["FINAL_OUTCOME"]}


def _observed_return(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise DataBlocked(f"{label}: fractional numeric return required")
    try:
        amount = float(value)
    except (ValueError, TypeError) as exc:
        raise DataBlocked(f"{label}: fractional return required") from exc
    from math import isfinite

    if not isfinite(amount) or amount <= -1:
        raise DataBlocked(f"{label}: return must be finite and above -100%")
    return amount


def _observed(data: dict[str, Any], *, decision_date: date, today: date) -> dict:
    if data.get("verified_by_operator") is not True:
        raise DataBlocked("official P&L must be operator-verified")
    if data.get("benchmark_id") != "WLS Index":
        raise DataBlocked("actual relative performance must use WLS Index")
    if not str(data.get("source", "")).strip():
        raise DataBlocked("actual TMSG source reference required")
    try:
        stamp = date.fromisoformat(data["observation_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DataBlocked("observation_date must be ISO date") from exc
    if not decision_date < stamp <= today:
        raise DataBlocked("observed outcome must occur after the decision and not in future")
    portfolio = _observed_return(data.get("portfolio_return"), "portfolio_return")
    wls = _observed_return(data.get("wls_return"), "wls_return")
    return {
        "observation_date": str(stamp),
        "portfolio_return": portfolio, "wls_return": wls,
        "relative_wealth": (1 + portfolio) / (1 + wls) - 1,
        "source": str(data["source"]), "verified_by_operator": True,
        "benchmark_id": "WLS Index",
    }


def _validate_event(
    kind: str, data: dict[str, Any], events: list[dict[str, Any]], *, today: date
) -> dict[str, Any]:
    if kind == "DECISION":
        report = data.get("simulation")
        if not isinstance(report, dict) or report.get("status") != "SIMULATION_ONLY":
            raise DataBlocked("DECISION must reference a completed simulation report")
        run = report.get("run_id")
        if not isinstance(run, str) or not run:
            raise DataBlocked("simulation report run_id required")
        if any(e["data"]["run_id"] == run for e in events if e["kind"] == "DECISION"):
            raise DataBlocked("run_id already committed")
        chosen = str(data.get("chosen_scenario", "")).upper()
        if chosen not in {"HOLD", "REBALANCE", "DEFENSIVE"}:
            raise DataBlocked("choose one of the three scenarios")
        try:
            at = date.fromisoformat(report["method"]["decision_date"])
        except (KeyError, ValueError, TypeError) as exc:
            raise DataBlocked("simulation decision date missing") from exc
        if at > today or at >= END_DATE:
            raise DataBlocked("cannot commit a future/expired decision")
        notes = str(data.get("note", "")).strip()
        if len(notes) > 2000:
            raise DataBlocked("decision note exceeds 2000 characters")
        return {
            "run_id": run, "decision_date": str(at), "chosen_scenario": chosen,
            "simulation_sha256": fingerprint(report),
            "input_sha256": report["input_sha256"],
            "registered_forecast_median": report["summaries"][chosen]["relative_wealth_median"],
            "registered_forecast_p10": report["summaries"][chosen]["relative_wealth_p10"],
            "registered_forecast_p90": report["summaries"][chosen]["relative_wealth_p90"],
            "note": notes, "simulation_only": True, "execution_authorized": False,
        }
    if kind not in {"CHECKPOINT", "FINAL_OUTCOME"}:
        raise DataBlocked("event kind unsupported")
    run = str(data.get("run_id", "")).strip()
    decisions = [e for e in events if e["kind"] == "DECISION" and e["data"]["run_id"] == run]
    if len(decisions) != 1:
        raise DataBlocked("unknown registered decision run_id")
    at = date.fromisoformat(decisions[0]["data"]["decision_date"])
    observed = _observed(data, decision_date=at, today=today)
    stamp = date.fromisoformat(observed["observation_date"])
    if kind == "CHECKPOINT" and stamp >= END_DATE:
        raise DataBlocked("checkpoints must precede 13 November")
    if kind == "FINAL_OUTCOME" and stamp != END_DATE:
        raise DataBlocked("full-horizon outcome requires verified 13 Nov date")
    if kind == "CHECKPOINT" and any(
        e["kind"] == "CHECKPOINT" and e["data"]["run_id"] == run
        and e["data"]["observation_date"] == observed["observation_date"]
        for e in events
    ):
        raise DataBlocked("duplicate checkpoint for date")
    if kind == "FINAL_OUTCOME" and any(
        e["kind"] == "FINAL_OUTCOME" and e["data"]["run_id"] == run
        for e in events
    ):
        raise DataBlocked("final outcome already recorded")
    observed["run_id"] = run
    observed["comparison_note"] = (
        "Intra-horizon diagnostic: NOT comparable with full-horizon forecast"
        if kind == "CHECKPOINT"
        else "Full-horizon forecast comparison; does not establish causality"
    )
    if kind == "FINAL_OUTCOME":
        observed["forecast_median_error"] = (
            observed["relative_wealth"] -
            decisions[0]["data"]["registered_forecast_median"]
        )
    return observed


def append_event(
    journal: str | Path,
    kind: str,
    data: dict[str, Any],
    *,
    root: str | Path = "outputs/gtc_twin",
    today: date | None = None,
) -> dict[str, Any]:
    """Local append-only write under exclusive lock, with no edit/delete endpoint."""
    if not isinstance(data, dict):
        raise DataBlocked("event data must be an object")
    path = _path_inside(journal, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise DataBlocked("journal in use: concurrent writer lock found") from exc
    try:
        os.close(fd)
        verify_journal(path, root=root)
        events = []
        if path.is_file():
            with path.open(encoding="utf-8") as handle:
                events = [json.loads(line) for line in handle]
        validated = _validate_event(
            kind, data, events, today=today or datetime.now(UTC).date()
        )
        prev = events[-1]["sha256"] if events else ZERO
        body = {
            "seq": len(events) + 1, "kind": kind,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "prev_sha256": prev, "data": validated,
        }
        record = {**body, "sha256": fingerprint(body)}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return {"status": "RECORDED", "seq": record["seq"],
                "kind": kind, "run_id": validated["run_id"],
                "sha256": record["sha256"], "journal": str(path)}
    finally:
        lock.unlink(missing_ok=True)
