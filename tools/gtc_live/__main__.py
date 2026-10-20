"""Explicitly offline, read-only CLI for verified challenge state."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.gtc_live.freshness import audit_freshness
from tools.gtc_live.horizon import remaining_horizon
from tools.gtc_live.ledger import DataBlocked, reconcile
from tools.gtc_live.performance import daily_relative_pnl
from tools.gtc_live.risk_gate import check_trade_plan
from tools.gtc_live.scenarios import stress_portfolio
from tools.gtc_live.session import assess_session


def read_json(filename: str) -> Any:
    with Path(filename).open(encoding="utf-8") as file:
        return json.load(file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only GTC live operations; never sends orders to Bloomberg."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reconcile", "pretrade", "freshness", "pnl", "horizon", "stress", "session"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--input", required=True, help="Local JSON source, never committed")
        if name == "freshness":
            cmd.add_argument("--file-root", default=None, help="Root for optional hash checks")
        if name == "horizon":
            cmd.add_argument(
                "--calendar", required=True, help="Verified exchange sessions JSON list"
            )
    return parser


def run(args: argparse.Namespace) -> Any:
    data = read_json(args.input)
    if args.command == "reconcile":
        return reconcile(data)
    if args.command == "pretrade":
        return check_trade_plan(data["snapshot"], data["proposals"])
    if args.command == "freshness":
        return audit_freshness(data, file_root=args.file_root)
    if args.command == "pnl":
        return daily_relative_pnl(data["start"], data["end"],
                                  data["benchmark_start"], data["benchmark_end"])
    if args.command == "horizon":
        return remaining_horizon(data["as_of_date"], read_json(args.calendar))
    if args.command == "stress":
        return stress_portfolio(data["snapshot"], data["scenarios"])
    if args.command == "session":
        return assess_session(data)
    raise DataBlocked("unsupported command")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = run(args)
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (DataBlocked, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        # Do not print holdings, raw input or confidential file contents on failure.
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
