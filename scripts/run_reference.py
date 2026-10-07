"""Run the data -> relative risk -> minimum-TE research reference pipeline."""

import argparse
import hashlib
import json
import subprocess
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from src.market_data import prepare_market_data
from src.optimisation import minimum_tracking_error
from src.risk_relative import estimate_relative_risk


def synthetic_inputs():
    """Deterministic test data only; no real security recommendations."""
    rng = np.random.default_rng(2026)
    dates = pd.date_range(end="2026-10-02", periods=53, freq="W-FRI")
    ids = [f"DEMO_{i}" for i in range(8)]
    returns = rng.normal(0.001, 0.02, (52, 8))
    prices = pd.DataFrame(
        np.vstack([np.ones(8), np.cumprod(1 + returns, axis=0)]) * 100, index=dates, columns=ids
    )
    bm_returns = returns @ np.full(8, 1 / 8)
    benchmark = pd.Series(np.r_[1, np.cumprod(1 + bm_returns)] * 1000, index=dates)
    universe = pd.DataFrame({"id": ids, "index_weight": np.full(8, 1 / 8)})
    common = {"verified": True, "evidence": "synthetic fixture", "available_at": "2026-10-02"}
    conventions = {
        "assets": {
            a: {
                **common,
                "currency": "USD",
                "price_unit_multiplier": 1,
                "adjustment": "split_adjusted_price",
            }
            for a in ids
        },
        "benchmark": {**common, "id": "WLS Index", "currency": "USD", "return_type": "price"},
    }
    return prices, benchmark, universe, conventions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--input", type=Path, default=Path("data/bloomberg/data"))
    parser.add_argument("--conventions", type=Path)
    parser.add_argument(
        "--candidates", type=Path, help="CSV with one id column; explicit candidate list"
    )
    parser.add_argument(
        "--fx", type=Path, help="Daily date + currency columns, USD per currency unit"
    )
    parser.add_argument("--as-of")
    parser.add_argument("--cutoff")
    parser.add_argument("--weeks", type=int, default=52)
    parser.add_argument("--min-observations", type=int, default=40)
    parser.add_argument("--max-age-days", type=int, default=4)
    parser.add_argument("--max-weight", type=float, default=0.18)
    parser.add_argument("--max-te-weekly", type=float)
    parser.add_argument(
        "--output", type=Path, required=True, help="New run directory (never overwritten)"
    )
    args = parser.parse_args()
    if args.demo and any([args.conventions, args.candidates, args.fx, args.as_of, args.cutoff]):
        parser.error("Demo has fixed synthetic inputs and dates; do not mix with real inputs.")
    if not args.demo and not all([args.conventions, args.candidates, args.as_of, args.cutoff]):
        parser.error("Real exports require --conventions, --candidates, --as-of and --cutoff.")
    if args.output.exists():
        parser.error("Choose a new output directory; previous runs are never overwritten.")
    report = {
        "ready_for_trading": False,
        "scope": "minimum_tracking_error_reference_only",
        "synthetic": args.demo,
        "as_of": "2026-10-07" if args.demo else args.as_of,
        "cutoff": "2026-10-02" if args.demo else args.cutoff,
        "parameters": {
            "weeks": args.weeks,
            "min_observations": args.min_observations,
            "max_age_days": args.max_age_days,
            "max_weight": args.max_weight,
            "max_te_weekly": args.max_te_weekly,
        },
        "source_sha256": {},
        "warnings": [
            "Reference weights only; no alpha, costs, cash reconciliation or executable orders.",
            "Annualized TE is weekly TE times sqrt(52), assuming no serial dependence.",
            "Current membership/weights cannot certify historical benchmark coverage.",
        ],
    }
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    report["git_revision"] = revision.stdout.strip() if revision.returncode == 0 else None
    worktree = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    report["git_dirty"] = bool(worktree.stdout.strip()) if worktree.returncode == 0 else None
    report["package_versions"] = {
        name: version(name) for name in ["pandas", "numpy", "scikit-learn", "cvxpy", "clarabel"]
    }
    project = Path(__file__).resolve().parents[1]
    report["code_sha256"] = {
        name: hashlib.sha256((project / name).read_bytes()).hexdigest()
        for name in [
            "src/market_data.py",
            "src/risk_relative.py",
            "src/covariance.py",
            "src/optimisation.py",
            "scripts/run_reference.py",
        ]
    }
    try:
        fx = None
        if args.demo:
            prices, benchmark, universe, conventions = synthetic_inputs()
        else:
            files = {
                "prices": args.input / "prices_10y.csv.gz",
                "benchmark": args.input / "benchmark_10y.csv",
                "universe": args.input / "universe.csv",
                "conventions": args.conventions,
                "candidates": args.candidates,
            }
            if args.fx:
                files["fx"] = args.fx
            report["source_sha256"] = {
                name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()
            }
            prices = pd.read_csv(files["prices"], index_col="date", parse_dates=True)
            benchmark = pd.read_csv(files["benchmark"], index_col="date", parse_dates=True)[
                "px_last"
            ]
            universe = pd.read_csv(files["universe"], dtype={"id": str})
            candidates = pd.read_csv(files["candidates"], dtype={"id": str})
            if (
                list(candidates.columns) != ["id"]
                or candidates.empty
                or candidates.id.isna().any()
                or candidates.id.duplicated().any()
            ):
                raise ValueError(
                    "Candidates require unique nonempty identifiers in a single id column."
                )
            if not set(candidates.id).issubset(set(universe.id)):
                raise ValueError("Candidate list contains non-WLS identifiers.")
            prices = prices.reindex(columns=candidates.id.tolist())
            conventions = json.loads(files["conventions"].read_text(encoding="utf-8"))
            if args.fx:
                fx = pd.read_csv(args.fx, index_col="date", parse_dates=True)
        prepared = prepare_market_data(
            prices,
            benchmark,
            universe,
            conventions,
            as_of=report["as_of"],
            cutoff=report["cutoff"],
            weeks=args.weeks,
            min_observations=args.min_observations,
            max_age_days=args.max_age_days,
            fx_usd=fx,
        )
        report["data"] = {
            "assets": list(prepared.returns_weekly_usd.columns),
            "exclusions": prepared.exclusions,
            "dropped_return_dates": prepared.dropped_return_dates,
            "current_benchmark_weight_covered": prepared.current_benchmark_weight_covered,
        }
        risk = estimate_relative_risk(
            prepared.returns_weekly_usd,
            prepared.benchmark_returns_weekly_usd,
            min_observations=args.min_observations,
        )
        report["risk"] = {
            "n_observations": risk.n_observations,
            "start": risk.observation_start,
            "end": risk.observation_end,
            "shrinkage": risk.shrinkage,
        }
        allocation = minimum_tracking_error(
            risk, max_weight=args.max_weight, max_tracking_error_weekly=args.max_te_weekly
        )
        report["allocation"] = {
            "solver_status": allocation.solver_status,
            "solver": allocation.solver,
            "tracking_error_weekly": allocation.tracking_error_weekly,
            "tracking_error_annualized_approx": allocation.tracking_error_annualized_approx,
            "max_constraint_violation": allocation.max_constraint_violation,
        }
        report["status"] = "reference_computed"
    except (ValueError, TypeError, KeyError, OSError) as exc:
        report["status"] = "blocked"
        report["error"] = str(exc)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )
    if report["status"] == "reference_computed":
        allocation.weights.to_csv(args.output / "reference_weights.csv", index_label="id")
        print(f"Research reference computed: {args.output}. Not certified for trading.")
        return 0
    print(f"Blocked: {report['error']}. Details: {args.output / 'report.json'}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
