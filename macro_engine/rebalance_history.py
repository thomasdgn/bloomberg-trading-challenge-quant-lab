"""D008 user addition, separate from the SPEC MVP; no performance evaluation.

python -m macro_engine.rebalance_history
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from macro_engine import config as cfg
from macro_engine.export import code_provenance, csv_bytes
from macro_engine.pit import calendar
from macro_engine.reference import load_reference
from macro_engine.run import compute_run


def rebalance_calendar(start=cfg.HISTORY_START, end=cfg.HISTORY_END) -> pd.DataFrame:
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if start.weekday() != 4 or end < start:
        raise ValueError(
            "A four-week calendar needs its requested Friday anchor and an ordered range."
        )
    nominal = pd.date_range(start, end, freq=f"{cfg.HORIZON_WEEKS}W-FRI")
    positions = calendar().searchsorted(nominal, side="right") - 1
    if (positions < 0).any():
        raise ValueError("Rebalance date outside NYSE calendar coverage.")
    return pd.DataFrame({"rebalance_date": nominal, "query_date": calendar()[positions]})


def compute_history(
    reference, *, start=cfg.HISTORY_START, end=cfg.HISTORY_END, progress=None
) -> pd.DataFrame:
    dates = rebalance_calendar(start, end)
    records = []
    provenance = code_provenance()
    for position, row in enumerate(dates.itertuples(index=False), 1):
        # compute_run truncates BOTH observations and publication/vintage dates.
        for run in compute_run(reference, row.query_date, "H", "strict"):
            if run.review_analogues.empty:
                status = (
                    "INSUFFICIENT_HISTORY"
                    if len(run.state.complete) < cfg.MIN_HISTORY_SESSIONS
                    else "INCOMPLETE_QUERY_STATE"
                    if row.query_date not in run.state.complete.index
                    else "NO_ELIGIBLE_EPISODE"
                )
                rows = [
                    {
                        "query_date": row.query_date,
                        "sample": "H",
                        "mode": "strict",
                        "ablation": run.ablation,
                        "rank": pd.NA,
                        "status": status,
                    }
                ]
            else:
                rows = run.review_analogues.to_dict("records")
            for item in rows:
                item.update(
                    rebalance_date=row.rebalance_date,
                    query_date=row.query_date,
                    status=item.get("status", "OK"),
                    selected_count=len(run.review_analogues),
                    reference_cache=cfg.REFERENCE_CACHE,
                    reference_manifest_sha256=cfg.REFERENCE_MANIFEST_SHA256,
                    git_commit=provenance["git_commit"],
                    holiday_rule=cfg.HISTORY_HOLIDAY_RULE,
                    horizon_weeks=cfg.HORIZON_WEEKS,
                    distance_quantile=cfg.DISTANCE_QUANTILE,
                    episode_separation_months=cfg.EPISODE_SEPARATION_MONTHS,
                    embargo_days=cfg.EMBARGO_CALENDAR_DAYS,
                )
                records.append(item)
        if progress is not None:
            progress(position, len(dates), row.rebalance_date, row.query_date)
    result = pd.DataFrame(records)
    for column in (
        "episode_start",
        "episode_end",
        "representative_date",
        "distance",
        "distance_mahalanobis",
        "stability_exact",
        "stability_episode",
        "stability_variants",
    ):
        if column not in result:
            result[column] = pd.NA
    if "rank" in result:
        result["rank"] = result["rank"].astype("Int64")
    return result.sort_values(["rebalance_date", "ablation", "rank"], kind="stable").reset_index(
        drop=True
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="D008: four-week H strict analogues, with/without news; no performance test."
    )
    parser.add_argument(
        "--output", type=Path, default=cfg.OUTPUT_ROOT / "history" / cfg.HISTORY_FILENAME
    )
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.is_relative_to(cfg.CACHE_ROOT.resolve()) or output.is_relative_to(
        cfg.MODULE_ROOT.resolve()
    ):
        raise ValueError("Historical output cannot write into cache or code.")
    if output.exists():
        raise FileExistsError("Historical output already exists; choose a new destination.")
    reference = load_reference()

    def progress(number, total, nominal, query):
        print(f"{number}/{total}: {nominal.date()} -> {query.date()}", flush=True)

    result = compute_history(reference, progress=progress)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(csv_bytes(result))
    print(f"Single long file: {output}; rows={len(result)}", flush=True)


if __name__ == "__main__":
    main()
