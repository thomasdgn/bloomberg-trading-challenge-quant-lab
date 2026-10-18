"""Filtered backtest comparison: blocked until the preregistration tag is verified."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from macro_engine import config as macro_cfg
from macro_engine.export import csv_bytes, sha256
from macro_engine.reference import reference_metadata
from research.macro_conditional_ic.common import join_labels, read_labels
from research.macro_filter_backtest import config as cfg
from research.macro_filter_backtest.mechanics import (
    blend,
    filter_activation,
    information_ratio,
    k_series,
    rotation,
    series_metrics,
    wealth,
)
from research.macro_filter_backtest.statistics import (
    conclusion,
    criterion,
    paired_difference,
    percentile_position,
    placebo_medians,
    sub_seed,
)

FROZEN = (
    "docs/macro_engine/PROTOCOLE_FILTRE_MACRO.md",
    "research/macro_filter_backtest/__init__.py",
    "research/macro_filter_backtest/config.py",
    "research/macro_filter_backtest/mechanics.py",
    "research/macro_filter_backtest/statistics.py",
    "research/macro_filter_backtest/run_base.py",
    "research/macro_filter_backtest/compute.py",
)


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=cfg.ROOT, text=True).strip()


def guard_preregistered() -> str:
    commit = git("rev-parse", f"{cfg.TAG}^{{commit}}")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=cfg.ROOT, check=True)
    for relative in FROZEN:
        frozen = subprocess.check_output(["git", "show", f"{cfg.TAG}:{relative}"], cwd=cfg.ROOT)
        current = (cfg.ROOT / relative).read_bytes()
        if frozen.replace(b"\r\n", b"\n") != current.replace(b"\r\n", b"\n"):
            raise ValueError(f"Preregistered file changed after the tag: {relative}")
    return commit


def load_base() -> tuple[pd.DataFrame, dict]:
    manifest = json.loads((cfg.BASE_RUN / "manifest.json").read_text(encoding="utf-8"))
    path = cfg.BASE_RUN / "periods.csv"
    if sha256(path.read_bytes()) != manifest["periods_sha256"]:
        raise ValueError("Base re-run periods changed since the run.")
    rerun = pd.read_csv(path, parse_dates=["date", "end_date"])
    audit = pd.read_csv(cfg.AUDIT_PERIODS, parse_dates=["date", "end_date"])
    if sha256(cfg.AUDIT_PERIODS.read_bytes()) != cfg.AUDIT_FILE_SHA256["periods.csv"]:
        raise ValueError("Audit periods changed.")
    pd.testing.assert_frame_equal(rerun, audit, check_exact=False, rtol=0, atol=1e-12)
    numeric = rerun.select_dtypes("number").columns
    difference = float((rerun[numeric] - audit[numeric]).abs().max().max())
    if sorted(rerun.offset.unique()) != list(cfg.OFFSETS):
        raise ValueError("Unexpected offsets in the base backtest.")
    return rerun.sort_values(["offset", "date"]).reset_index(drop=True), {
        "base_run_manifest": manifest,
        "rerun_equals_audit_bytes": sha256(path.read_bytes())
        == cfg.AUDIT_FILE_SHA256["periods.csv"],
        "rerun_vs_audit_max_abs_difference": difference,
    }


def load_labels() -> pd.DataFrame:
    reference_metadata()  # SPEC and D006 reference manifest hashes, fail closed.
    path = cfg.LABEL_DIRECTORY / "macro_regimes.csv"
    if sha256(path.read_bytes()) != cfg.LABELS_SHA256:
        raise ValueError("Labels differ from the approved H strict export.")
    return read_labels()


def build_series(base: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, missing_rows = [], []
    for ablation in cfg.ABLATIONS:
        joined = join_labels(base[["date", "offset"]], labels, ablation)
        joined = base.merge(joined, on=["date", "offset"], validate="one_to_one")
        if not joined.date.gt(joined.macro_date).all():
            raise ValueError("A decision uses a same-day or future macro label.")
        for offset, group in joined.groupby("offset", sort=True):
            group = group.sort_values("date").reset_index(drop=True)
            portfolio = group[cfg.RETURN].to_numpy(float)
            benchmark = group[cfg.BENCHMARK].to_numpy(float)
            for variant in cfg.VARIANTS:
                if variant == "base":
                    active, missing = np.zeros(len(group), bool), 0
                elif variant == "T":
                    active, missing = np.ones(len(group), bool), 0
                else:
                    active, missing = filter_activation(group, cfg.FILTERS[variant])
                    flags = group[list(cfg.FILTERS[variant])].astype("boolean")
                    missing_rows.extend(
                        {"ablation": ablation, "variant": variant, "offset": offset, "date": date}
                        for date in group.date[flags.isna().any(axis=1).to_numpy()]
                    )
                k = k_series(active)
                returns, cost = blend(portfolio, benchmark, k)
                strategy_wealth, benchmark_wealth = wealth(returns)[1:], wealth(benchmark)[1:]
                relative = strategy_wealth / benchmark_wealth
                frame = pd.DataFrame(
                    {
                        "ablation": ablation,
                        "variant": variant,
                        "offset": offset,
                        "date": group.date,
                        "end_date": group.end_date,
                        "macro_date": group.macro_date,
                        "filter_active": active,
                        "k": k,
                        "missing_labels": missing if variant in cfg.FILTERS else 0,
                        "portfolio_return": portfolio,
                        "wls_return": benchmark,
                        "return": returns,
                        "switch_cost": cost,
                        "active_return": returns - benchmark,
                        "wealth": strategy_wealth,
                        "wls_wealth": benchmark_wealth,
                        "relative_wealth": relative,
                        "relative_drawdown": relative
                        / np.maximum.accumulate(np.r_[1.0, relative])[1:]
                        - 1.0,
                        "rotation": rotation(group.one_way_turnover.to_numpy(float), k),
                        "base_one_way_turnover": group.one_way_turnover,
                    }
                )
                for label in sorted({name for names in cfg.FILTERS.values() for name in names}):
                    frame[label] = group[label].astype("boolean")
                rows.append(frame)
    return pd.concat(rows, ignore_index=True), pd.DataFrame(missing_rows)


def metrics_by_offset(series: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ablation, variant, offset), group in series.groupby(
        ["ablation", "variant", "offset"], sort=False
    ):
        metrics = series_metrics(
            group["return"], group.wls_return, group.k, group.base_one_way_turnover
        )
        rows.append(
            {
                "ablation": ablation,
                "variant": variant,
                "offset": offset,
                "start": group.date.min().date().isoformat(),
                "end": group.end_date.max().date().isoformat(),
                **metrics,
                "missing_label_periods": int(group.missing_labels.iloc[0]),
            }
        )
    return pd.DataFrame(rows)


def yearly(series: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keys = ["ablation", "variant", "offset", series.date.dt.year.rename("year")]
    for (ablation, variant, offset, year), group in series.groupby(keys, sort=False):
        strategy = float(np.prod(1 + group["return"]) - 1)
        benchmark = float(np.prod(1 + group.wls_return) - 1)
        rows.append(
            {
                "ablation": ablation,
                "variant": variant,
                "offset": offset,
                "year": int(year),
                "periods": len(group),
                "filtered_periods": int((group.k < 1).sum()),
                "net_return": strategy,
                "wls_return": benchmark,
                "active_return_pp": strategy - benchmark,
                "information_ratio": information_ratio(group.active_return),
                "hit_rate": float((group.active_return > 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def bootstrap(series: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ablation, offset), group in series.groupby(["ablation", "offset"], sort=False):
        base = group.loc[group.variant.eq("base")].sort_values("date")
        for variant in cfg.VARIANTS[1:]:
            selected = group.loc[group.variant.eq(variant)].sort_values("date")
            observed_ir = information_ratio(selected.active_return) - information_ratio(
                base.active_return
            )
            observed_mean = (
                selected.active_return.mean() - base.active_return.mean()
            ) * cfg.PERIODS_PER_YEAR
            interval = paired_difference(
                selected.active_return.to_numpy(float),
                base.active_return.to_numpy(float),
                seed=sub_seed(cfg.BOOTSTRAP_SEED, ablation, variant, offset),
            )
            rows.append(
                {
                    "ablation": ablation,
                    "variant": variant,
                    "offset": offset,
                    "delta_ir": observed_ir,
                    "delta_mean_active": observed_mean,
                    **interval,
                }
            )
    return pd.DataFrame(rows)


def placebo(series: pd.DataFrame, metrics: pd.DataFrame):
    distributions, summary, criteria = [], [], {}
    for ablation in cfg.ABLATIONS:
        subset = series.loc[series.ablation.eq(ablation)]
        base = subset.loc[subset.variant.eq("base")]
        per_offset = {
            offset: (group.portfolio_return.to_numpy(float), group.wls_return.to_numpy(float))
            for offset, group in base.sort_values("date").groupby("offset")
        }
        medians = (
            metrics.loc[metrics.ablation.eq(ablation)]
            .groupby("variant")
            .information_ratio.median()
            .to_dict()
        )
        for reference in cfg.FILTERS:
            activation = {
                offset: group.filter_active.to_numpy(bool)
                for offset, group in subset.loc[subset.variant.eq(reference)]
                .sort_values("date")
                .groupby("offset")
            }
            draws, counts = placebo_medians(
                per_offset,
                activation,
                seed=sub_seed(cfg.PLACEBO_SEED, ablation, reference),
                draws=cfg.PLACEBO_DRAWS,
            )
            for offset, values in counts.items():
                if set(values) != {int(activation[offset].sum())}:
                    raise ValueError("Placebo activation frequency differs from the filter.")
            distributions.append(
                pd.DataFrame(
                    {
                        "ablation": ablation,
                        "placebo_reference": reference,
                        "draw": np.arange(cfg.PLACEBO_DRAWS),
                        "median_information_ratio": draws,
                    }
                )
            )
            for variant in cfg.FILTERS:
                summary.append(
                    {
                        "ablation": ablation,
                        "placebo_reference": reference,
                        "decisional": reference == cfg.PRIMARY and variant == cfg.PRIMARY,
                        "frequency_matched": reference == variant,
                        "variant": variant,
                        "median_information_ratio": medians[variant],
                        "placebo_q95": float(np.quantile(draws, cfg.PLACEBO_QUANTILE)),
                        "placebo_median": float(np.median(draws)),
                        "percentile_in_placebo": percentile_position(medians[variant], draws),
                        "activations_by_offset": json.dumps(
                            {str(k): int(v.sum()) for k, v in activation.items()}
                        ),
                    }
                )
            if reference == cfg.PRIMARY:
                criteria[ablation] = {"medians": medians, **criterion(medians, draws)}
    verdict = conclusion({ablation: criteria[ablation]["met"] for ablation in cfg.ABLATIONS})
    return pd.concat(distributions, ignore_index=True), pd.DataFrame(summary), criteria, verdict


def main() -> None:
    commit = guard_preregistered()
    results = cfg.OUTPUT / "results"
    if results.exists():
        raise FileExistsError(f"{results} exists; no silent overwrite.")
    base, base_provenance = load_base()
    labels = load_labels()
    series, missing = build_series(base, labels)
    metrics = metrics_by_offset(series)
    by_year = yearly(series)
    print("Bootstrap of F - base differences...", flush=True)
    intervals = bootstrap(series)
    print("Placebo draws...", flush=True)
    draws, placebo_summary, criteria, verdict = placebo(series, metrics)
    results.mkdir(parents=True)
    tables = {
        "series.csv": series,
        "metrics_by_offset.csv": metrics,
        "metrics_by_year.csv": by_year,
        "bootstrap_differences.csv": intervals,
        "placebo_draws.csv": draws,
        "placebo_summary.csv": placebo_summary,
        "missing_labels.csv": missing,
    }
    for name, frame in tables.items():
        (results / name).write_bytes(csv_bytes(frame))
    decision = {"tag": cfg.TAG, "tag_commit": commit, "criteria": criteria, "conclusion": verdict}
    (results / "criterion.json").write_text(
        json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "head_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "tag": cfg.TAG,
        "tag_commit": commit,
        "python": sys.version.split()[0],
        "versions": {"numpy": np.__version__, "pandas": pd.__version__},
        **base_provenance,
        "labels_sha256": cfg.LABELS_SHA256,
        "reference_cache": macro_cfg.REFERENCE_CACHE,
        "output_sha256": {
            name: sha256((results / name).read_bytes()) for name in [*tables, "criterion.json"]
        },
    }
    (results / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Results written to {results}; conclusion: {verdict}", flush=True)


if __name__ == "__main__":
    main()
