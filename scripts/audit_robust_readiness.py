"""Read-only coverage diagnostic; this does not validate prices or generate trades."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def audit(root: Path, as_of: str, cutoff: str, weeks: int, min_observations: int) -> dict:
    if weeks < 1 or not 1 <= min_observations <= weeks:
        raise ValueError("Require 1 <= min_observations <= weeks.")
    cutoff_date, as_of_date = pd.Timestamp(cutoff), pd.Timestamp(as_of)
    if cutoff_date > as_of_date or cutoff_date.dayofweek != 4:
        raise ValueError("The diagnostic cutoff must be a Friday no later than as_of.")
    files = {
        "universe": root / "universe.csv",
        "features": root / "features_snapshot.csv",
        "prices": root / "prices_10y.csv.gz",
        "benchmark": root / "benchmark_10y.csv",
    }
    universe = pd.read_csv(files["universe"])
    features = pd.read_csv(files["features"])
    prices = pd.read_csv(files["prices"], index_col="date", parse_dates=True)
    benchmark = pd.read_csv(files["benchmark"], index_col="date", parse_dates=True)
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError("Historical dates must be unique and ordered.")
    if universe["id"].duplicated().any():
        raise ValueError("Universe identifiers must be unique.")
    weekly = prices.loc[:cutoff_date].resample("W-FRI").last().tail(weeks + 1)
    returns = weekly.pct_change(fill_method=None).iloc[1:]
    eligible = returns.columns[returns.notna().sum() >= min_observations]
    complete = returns.columns[returns.notna().sum() == weeks]
    return {
        "as_of": as_of,
        "ready_for_trading": False,
        "warning": (
            "Coverage diagnostic only: currencies and adjustments remain unverified; "
            "resample last skips missing prices within a week. No freshness validation."
        ),
        "source_sha256": {
            key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in files.items()
        },
        "universe_count": len(universe),
        "historical_count": prices.shape[1],
        "current_benchmark_weight_covered_pct": float(
            universe.loc[universe.id.isin(prices.columns), "index_weight_pct"].sum()
        ),
        "daily_start": str(prices.index.min().date()),
        "daily_end": str(prices.index.max().date()),
        "last_completed_week": str(returns.index.max().date()),
        "weekly_observations_diagnostic": len(returns),
        "minimum_observations_required": min_observations,
        "assets_meeting_minimum_observations": len(eligible),
        "assets_with_all_weekly_returns": len(complete),
        "joint_complete_weeks_for_eligible_assets": (
            int(returns[eligible].notna().all(axis=1).sum()) if len(eligible) else 0
        ),
        "joint_complete_weeks_all_historical_assets": int(returns.notna().all(axis=1).sum()),
        "nonpositive_prices_count": int((prices <= 0).sum().sum()),
        "feature_columns": list(features.columns),
        "missing_by_feature": {c: int(features[c].isna().sum()) for c in features.columns},
        "benchmark_last_observation": str(benchmark.dropna().index.max().date()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/bloomberg/data"))
    parser.add_argument("--as-of", default="2026-10-07")
    parser.add_argument("--cutoff", default="2026-10-02")
    parser.add_argument("--weeks", type=int, default=52)
    parser.add_argument("--min-observations", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.input, args.as_of, args.cutoff, args.weeks, args.min_observations)
    if args.output.exists():
        parser.error("Choose a new report path; existing reports are not overwritten.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Coverage report: {args.output}; readiness for trading is not certified.")


if __name__ == "__main__":
    main()
