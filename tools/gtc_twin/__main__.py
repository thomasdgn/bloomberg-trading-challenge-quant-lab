"""Offline Digital Twin command line. No trading endpoints or account access."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.engine import fingerprint, simulate
from tools.gtc_twin.journal import append_event, verify_journal
from tools.gtc_twin.report import render_html


def read_json(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        content = json.load(handle, parse_constant=lambda name: (_ for _ in ()).throw(
            DataBlocked(f"JSON invalid non-finite constant: {name}")
        ))
    if not isinstance(content, dict):
        raise DataBlocked("input JSON root must be an object")
    return content


def _under_output_root(path: str | Path) -> Path:
    root = Path("outputs/gtc_twin").resolve()
    destination = Path(path).resolve()
    if destination == root or not destination.is_relative_to(root):
        raise DataBlocked("write output only below ignored outputs/gtc_twin/")
    return destination


def _write_run(folder: str, result: dict[str, Any]) -> dict[str, Any]:
    output = _under_output_root(folder)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwrite even if stale run exists.
    output.mkdir(exist_ok=False)
    result_bytes = json.dumps(
        result, indent=2, ensure_ascii=False, sort_keys=True,
        allow_nan=False,
    ) + "\n"
    try:
        with (output / "simulation.json").open("x", encoding="utf-8") as file:
            file.write(result_bytes)
        with (output / "report.html").open("x", encoding="utf-8") as file:
            file.write(render_html(result))
        with (output / "manifest.json").open("x", encoding="utf-8") as file:
            json.dump({
                "status": "SIMULATION_ONLY", "run_id": result["run_id"],
                "input_sha256": result["input_sha256"],
                "simulation_sha256": fingerprint(result),
                "report_sha256": fingerprint(render_html(result)),
                "execution_authorized": False,
            }, file, indent=2)
            file.write("\n")
    except Exception:
        # An interrupted incomplete output is retained for investigation,
        # never silently reused/overwritten by a subsequent run.
        raise
    return {
        "status": "SIMULATION_ONLY", "run_id": result["run_id"],
        "output_dir": str(output), "execution_authorized": False,
        "html_report": str(output / "report.html"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GTC Digital Twin (offline, no orders)")
    commands = parser.add_subparsers(dest="action", required=True)
    simulation = commands.add_parser("simulate", help="Research scenario comparison")
    simulation.add_argument("--input", required=True, help="Verified private JSON")
    simulation.add_argument("--output", required=True, help="New directory under outputs/gtc_twin/")
    decision = commands.add_parser("record-decision", help="Append sealed research decision")
    decision.add_argument("--report", required=True, help="simulation.json path")
    decision.add_argument("--journal", required=True, help="Journal under outputs/gtc_twin/")
    decision.add_argument("--chosen", required=True, choices=["HOLD", "REBALANCE", "DEFENSIVE"])
    decision.add_argument("--note", default="")
    for name in ("record-checkpoint", "record-final"):
        cmd = commands.add_parser(name, help="Append verified realized TMSG outcome")
        cmd.add_argument("--input", required=True)
        cmd.add_argument("--journal", required=True)
    verify = commands.add_parser("verify-journal", help="Check journal chain, no edits")
    verify.add_argument("--journal", required=True)
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.action == "simulate":
        return _write_run(args.output, simulate(read_json(args.input)))
    if args.action == "record-decision":
        report = read_json(args.report)
        return append_event(
            args.journal, "DECISION",
            {"simulation": report, "chosen_scenario": args.chosen, "note": args.note},
        )
    if args.action == "record-checkpoint":
        return append_event(args.journal, "CHECKPOINT", read_json(args.input))
    if args.action == "record-final":
        return append_event(args.journal, "FINAL_OUTCOME", read_json(args.input))
    if args.action == "verify-journal":
        return verify_journal(args.journal)
    raise DataBlocked("unsupported CLI action")


def main(argv: list[str] | None = None) -> int:
    try:
        result = execute(build_parser().parse_args(argv))
        print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
        return 0
    except (
        DataBlocked, ValueError, OSError, KeyError, TypeError, json.JSONDecodeError,
    ) as exc:
        print(json.dumps(
            {"status": "BLOCKED", "reason": str(exc)},
            ensure_ascii=False,
        ), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
