"""Decision journal test cases: hash chain, duplicates, date integrity, outcomes."""
from __future__ import annotations

import json
from datetime import date

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.engine import simulate
from tools.gtc_twin.journal import append_event, verify_journal


def _checkpoint(run: str, day: str = "2026-10-22") -> dict:
    return {
        "run_id": run, "observation_date": day,
        "verified_by_operator": True, "source": "SYNTHETIC_TMSG",
        "benchmark_id": "WLS Index",
        "portfolio_return": 0.011, "wls_return": 0.009,
    }


def test_append_decision_and_checkpoint_verified_chain(example_payload, tmp_path) -> None:
    journal = tmp_path / "history.jsonl"
    simulation = simulate(example_payload)
    one = append_event(journal, "DECISION", {
        "simulation": simulation, "chosen_scenario": "HOLD",
        "note": "Research hypothesis, no execution",
    }, root=tmp_path, today=date(2026, 10, 22))
    assert one["seq"] == 1
    two = append_event(journal, "CHECKPOINT", _checkpoint(simulation["run_id"]),
                       root=tmp_path, today=date(2026, 10, 22))
    assert two["seq"] == 2
    outcome = verify_journal(journal, root=tmp_path)
    assert outcome["decisions"] == 1
    assert outcome["checkpoints"] == 1
    assert outcome["events"] == 2
    assert outcome["last_sha256"] == two["sha256"]
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert events[1]["data"]["comparison_note"].startswith("Intra-horizon")
    assert "forecast_median_error" not in events[1]["data"]


def test_duplicates_and_future_outcomes_are_blocked(example_payload, tmp_path) -> None:
    journal = tmp_path / "log.jsonl"
    simulation = simulate(example_payload)
    decision = {"simulation": simulation, "chosen_scenario": "REBALANCE"}
    append_event(journal, "DECISION", decision, root=tmp_path,
                 today=date(2026, 10, 22))
    with pytest.raises(DataBlocked, match="already committed"):
        append_event(journal, "DECISION", decision, root=tmp_path,
                     today=date(2026, 10, 22))
    with pytest.raises(DataBlocked, match="requires verified 13 Nov"):
        append_event(journal, "FINAL_OUTCOME",
                     _checkpoint(simulation["run_id"]), root=tmp_path,
                     today=date(2026, 11, 14))
    with pytest.raises(DataBlocked, match="not in future"):
        append_event(journal, "CHECKPOINT",
                     _checkpoint(simulation["run_id"], "2026-10-30"),
                     root=tmp_path, today=date(2026, 10, 22))


def test_final_outcome_comparison_only_on_challenge_end(example_payload, tmp_path) -> None:
    journal = tmp_path / "log.jsonl"
    simulation = simulate(example_payload)
    append_event(journal, "DECISION",
                 {"simulation": simulation, "chosen_scenario": "DEFENSIVE"},
                 root=tmp_path, today=date(2026, 10, 22))
    append_event(
        journal, "FINAL_OUTCOME",
        _checkpoint(simulation["run_id"], "2026-11-13"),
        root=tmp_path, today=date(2026, 11, 13),
    )
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert events[1]["data"]["forecast_median_error"] == pytest.approx(
        events[1]["data"]["relative_wealth"] -
        events[0]["data"]["registered_forecast_median"]
    )
    assert verify_journal(journal, root=tmp_path)["final_outcomes"] == 1


def test_tampering_is_detected(example_payload, tmp_path) -> None:
    journal = tmp_path / "history.jsonl"
    simulation = simulate(example_payload)
    append_event(journal, "DECISION",
                 {"simulation": simulation, "chosen_scenario": "HOLD"},
                 root=tmp_path, today=date(2026, 10, 22))
    content = journal.read_text()
    journal.write_text(content.replace("HOLD", "OTHER"))
    with pytest.raises(DataBlocked, match="hash chain"):
        verify_journal(journal, root=tmp_path)


def test_private_journal_cannot_escape_root(example_payload, tmp_path) -> None:
    simulation = simulate(example_payload)
    with pytest.raises(DataBlocked, match="within ignored"):
        append_event(tmp_path.parent / "outside.jsonl", "DECISION", {
            "simulation": simulation, "chosen_scenario": "HOLD",
        }, root=tmp_path, today=date(2026, 10, 22))


def test_operator_verification_is_mandatory(example_payload, tmp_path) -> None:
    journal = tmp_path / "record.jsonl"
    simulation = simulate(example_payload)
    append_event(journal, "DECISION",
                 {"simulation": simulation, "chosen_scenario": "HOLD"},
                 root=tmp_path, today=date(2026, 10, 22))
    checkpoint = _checkpoint(simulation["run_id"])
    checkpoint["verified_by_operator"] = False
    with pytest.raises(DataBlocked, match="verified"):
        append_event(journal, "CHECKPOINT", checkpoint,
                     root=tmp_path, today=date(2026, 10, 22))
