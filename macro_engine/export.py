"""Section 11 artifacts; generated inputs and raw exports stay outside Git."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from macro_engine import config as cfg
from macro_engine.pit import next_session, snapshot
from macro_engine.reference import reference_metadata


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def finite_parameters(series: pd.Series) -> dict:
    return {name: None if pd.isna(value) else float(value) for name, value in series.items()}


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format=cfg.CSV_FLOAT_FORMAT,
        date_format=cfg.CSV_DATE_FORMAT,
    ).encode("utf-8")


def code_provenance() -> dict:
    root = cfg.MODULE_ROOT.parent
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
    )
    return {
        "git_commit": commit,
        "git_dirty": dirty,
        "module_sha256": {
            path.name: sha256(path.read_bytes()) for path in sorted(cfg.MODULE_ROOT.glob("*.py"))
        },
        "requirements_sha256": sha256((cfg.MODULE_ROOT / "requirements.txt").read_bytes()),
    }


def daily_frame(frame: pd.DataFrame, run) -> pd.DataFrame:
    result = frame.reset_index()
    result.insert(1, "sample", run.state.sample)
    result.insert(2, "mode", run.state.mode)
    result.insert(3, "ablation", run.ablation)
    result.insert(4, "as_of_date", run.state.query_date)
    return result


def current_registry(runs, reference_registry: pd.DataFrame) -> pd.DataFrame:
    rows = []
    definitions = {series.identifier: series for series in cfg.SERIES}
    indexed = reference_registry.set_index("identifier")
    for run in runs:
        for name in run.state.values:
            row = indexed.loc[name].to_dict()
            definition = definitions[name]
            row.update(
                identifier=name,
                sample=run.state.sample,
                mode=run.state.mode,
                ablation=run.ablation,
                reference_cache=cfg.REFERENCE_CACHE,
                reference_registry_sha256=cfg.REFERENCE_REGISTRY_SHA256,
                provider=definition.provider,
                pit_status=run.state.statuses[name],
                availability_rule=definition.availability_rule,
                availability_applied=True,
            )
            if name == "DTWEXBGS":
                row["limitations"] = (
                    "D003: retrospective only; no ALFRED dollar intervals in the pinned cache; "
                    "no strict R or index splicing."
                )
                row["pit_rule_requires_decision"] = False
                row["pit_capability"] = "retrospective_descriptive_only"
            if run.state.mode == "descriptive" and name in ("CPIAUCNS", "UNRATE"):
                row["availability_rule"] = (
                    "Revised vintage known at query date; historical placement by first release."
                )
            rows.append(row)
    return pd.DataFrame(rows)


def raw_frame(reference, runs, registry) -> pd.DataFrame:
    """Archived current-series inputs, never mislabeled as historical PIT data."""
    source = registry.set_index(["ablation", "identifier"])
    parts = []
    for run in runs:
        for name in run.state.values:
            raw = reference.observations[name]
            raw = raw.loc[raw.date <= run.state.query_date].copy()
            raw["identifier"], raw["ablation"] = name, run.ablation
            raw["sample"], raw["mode"] = run.state.sample, run.state.mode
            raw["source"] = source.loc[(run.ablation, name), "provider"]
            raw["downloaded_at_utc"] = source.loc[(run.ablation, name), "downloaded_at_utc"]
            raw["reference_cache"] = cfg.REFERENCE_CACHE
            raw["record_role"] = "reference_archive_not_a_pit_signal"
            parts.append(raw)
    return pd.concat(parts, ignore_index=True)


def pit_frame(reference, runs, registry) -> pd.DataFrame:
    """Raw observations with availability/vintage lineage, not transformed states."""
    source = registry.set_index(["ablation", "identifier"])
    parts = []
    for run in runs:
        query = run.state.query_date
        cut = reference.truncated(query)
        for name in run.state.values:
            raw = cut.observations[name].dropna(subset=["value"]).copy()
            if name in ("CPIAUCNS", "UNRATE") and name in cut.vintages:
                vintage = cut.vintages[name]
                raw = vintage.copy() if run.state.mode == "strict" else snapshot(vintage, query)
                raw = raw.dropna(subset=["value"]).copy()
                raw["available_at"] = pd.to_datetime(raw.realtime_start)
                raw["vintage"] = raw.realtime_start
                raw["realtime_end"] = raw.realtime_end.clip(upper=query.strftime("%Y-%m-%d"))
            elif name in ("CPIAUCNS", "UNRATE", "GPR", "EPU"):
                delay = (
                    cfg.CPI_FALLBACK_DAYS
                    if name == "CPIAUCNS"
                    else cfg.UNEMPLOYMENT_FALLBACK_DAYS
                    if name == "UNRATE"
                    else cfg.NEWS_PUBLICATION_DELAY_DAYS
                )
                raw["available_at"] = raw.date.dt.to_period("M").dt.to_timestamp(
                    how="end"
                ).dt.normalize() + pd.Timedelta(days=delay)
            elif name == "DCOILWTICO":
                raw = raw.groupby(raw.date.dt.to_period("M"), sort=True).tail(1).copy()
                ends = raw.date.dt.to_period("M").dt.to_timestamp(how="end").dt.normalize()
                raw["available_at"] = next_session(next_session(ends))
            elif name == "DTWEXBGS":
                raw["available_at"] = query  # D003, no invented publication date.
            else:
                raw["available_at"] = next_session(raw.date)
            raw = raw.loc[raw.available_at <= query].copy()
            raw["identifier"], raw["sample"], raw["mode"] = name, run.state.sample, run.state.mode
            raw["ablation"], raw["pit_status"] = run.ablation, run.state.statuses[name]
            raw["source"] = source.loc[(run.ablation, name), "provider"]
            raw["downloaded_at_utc"] = source.loc[(run.ablation, name), "downloaded_at_utc"]
            if "vintage" not in raw:
                raw["vintage"] = cfg.REFERENCE_CACHE
            parts.append(raw)
    return pd.concat(parts, ignore_index=True)


def validate_runs(runs):
    if not runs:
        raise ValueError("No runs to export.")
    identity = {(run.state.sample, run.state.mode, run.state.query_date) for run in runs}
    if len(identity) != 1:
        raise ValueError("Never combine different samples, modes or query dates.")
    for run in runs:
        if run.state.mode == "strict":
            present = run.state.values.notna()
            for name in run.state.values:
                known = run.state.available_at.loc[present[name], name]
                if known.isna().any() or (known > known.index).any():
                    raise ValueError("Strict state contains an availability violation.")


def export_run(reference, runs, destination: Path) -> dict:
    from macro_engine.diagnostics import render_diagnostics

    validate_runs(runs)
    destination = Path(destination).resolve()
    if (
        destination.is_relative_to(cfg.CACHE_ROOT.resolve())
        or destination.is_relative_to(cfg.MODULE_ROOT.resolve())
        or ".git" in destination.parts
    ):
        raise ValueError("Exports cannot write into cache, code or Git metadata.")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            "Output directory must be empty; existing artifacts are never overwritten."
        )
    # Reverify metadata, and use only the reference already hash-verified on load.
    reference_manifest, reference_registry = reference_metadata()
    registry = current_registry(runs, reference_registry)
    tables = {
        "macro_raw.parquet": raw_frame(reference, runs, registry),
        "macro_pit.parquet": pit_frame(reference, runs, registry),
        "macro_state_daily.parquet": pd.concat(
            [daily_frame(run.state.values, run) for run in runs], ignore_index=True
        ),
        "macro_regimes.csv": pd.concat(
            [daily_frame(run.labels, run) for run in runs], ignore_index=True
        ),
        "historical_analogues.csv": pd.concat(
            [run.review_analogues for run in runs], ignore_index=True
        ),
        "source_registry.csv": registry,
    }
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, frame in tables.items():
        payload = (
            frame.to_parquet(index=False, compression=cfg.PARQUET_COMPRESSION)
            if name.endswith(".parquet")
            else csv_bytes(frame)
        )
        with (destination / name).open("xb") as handle:
            handle.write(payload)
        hashes[name] = sha256(payload)
    html = render_diagnostics(reference, runs, registry).encode("utf-8")
    with (destination / "macro_diagnostics.html").open("xb") as handle:
        handle.write(html)
    hashes["macro_diagnostics.html"] = sha256(html)
    manifest = {
        "execution_date_utc": datetime.now(UTC).date().isoformat(),
        "query_date": runs[0].state.query_date.strftime("%Y-%m-%d"),
        "sample": runs[0].state.sample,
        "mode": runs[0].state.mode,
        "ablations": [run.ablation for run in runs],
        "reference_cache": cfg.REFERENCE_CACHE,
        "spec_sha256": cfg.SPEC_SHA256,
        "reference_manifest_sha256": cfg.REFERENCE_MANIFEST_SHA256,
        "reference_registry_sha256": cfg.REFERENCE_REGISTRY_SHA256,
        "raw_sha256": {
            artifact["file"]: artifact["sha256"] for artifact in reference_manifest["artifacts"]
        },
        "parameters": {
            name: getattr(cfg, name)
            for name in (
                "HORIZON_WEEKS",
                "EMBARGO_CALENDAR_DAYS",
                "MIN_HISTORY_SESSIONS",
                "EPISODE_GAP_SESSIONS",
                "EPISODE_SEPARATION_MONTHS",
                "DISTANCE_QUANTILE",
                "SENSITIVITY_SEPARATIONS_MONTHS",
                "SENSITIVITY_QUANTILES",
                "REGIME_PERCENTILES",
                "REGIME_RULES",
                "VOLATILITY_WINDOW_SESSIONS",
                "ANNUALIZATION_SESSIONS",
                "STANDARDIZATION_DDOF",
                "REALIZED_VOLATILITY_DDOF",
                "RATE_CHANGE_SESSIONS",
                "DOLLAR_CHANGE_SESSIONS",
                "CPI_CHANGE_MONTHS",
                "UNEMPLOYMENT_CHANGE_MONTHS",
                "OIL_CHANGE_MONTHS",
                "CPI_FALLBACK_DAYS",
                "UNEMPLOYMENT_FALLBACK_DAYS",
                "NEWS_PUBLICATION_DELAY_DAYS",
                "DAILY_PUBLICATION_DELAY_BUSINESS_DAYS",
                "OIL_ADDITIONAL_BUSINESS_DAYS",
            )
        },
        "normalization": {
            run.ablation: {
                "center": finite_parameters(run.analogues.normalized.center),
                "scale": finite_parameters(run.analogues.normalized.scale),
                "weights": run.analogues.normalized.weights.to_dict(),
            }
            for run in runs
        },
        "versions": {name: version(name) for name in cfg.REQUIREMENT_PACKAGES},
        "python": platform.python_version(),
        "code": code_provenance(),
        "output_sha256": hashes,
        "raw_export_role": (
            "Reference archive, including revised current-series values; "
            "never use macro_raw as a historical PIT signal."
        ),
        "join_rule": (
            "Join by decision date, sample, mode and ablation; "
            "prediction date must be strictly later than macro decision date."
        ),
    }
    with (destination / cfg.MANIFEST_FILENAME).open("xb") as handle:
        handle.write(
            (
                json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
                + "\n"
            ).encode("utf-8")
        )
    return manifest
