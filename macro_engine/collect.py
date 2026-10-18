"""Collect and archive raw inputs only; no PIT vectors or transformations yet.

Usage: python -m macro_engine.collect [--sp500-bloomberg export.csv]
Every run uses a new UTC timestamp directory. Existing cache files are never
overwritten. The source registry describes PIT capabilities, not computed
availability dates: the latter belong to the next, separately reviewed step.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from macro_engine import config as cfg


class CollectionError(RuntimeError):
    """A source could not be collected or did not match its declared schema."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


@dataclass
class CacheRun:
    """Append-only run directory; exclusive creation also protects old outputs."""

    root: Path
    downloaded_at: datetime

    @classmethod
    def create(cls, cache_root: Path = cfg.CACHE_ROOT) -> CacheRun:
        now = _utc_now()
        path = cache_root / now.strftime("%Y%m%dT%H%M%S.%fZ")
        path.mkdir(parents=True, exist_ok=False)
        return cls(path, now)

    def write_bytes(self, name: str, payload: bytes) -> Path:
        if self.root.resolve() == (cfg.CACHE_ROOT / cfg.REFERENCE_CACHE).resolve():
            raise CollectionError("D006: the reference cache is read-only.")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise CollectionError("Cache filename must be a simple relative filename.")
        path = self.root / name
        with path.open("xb") as handle:
            handle.write(payload)
        return path

    def write_json(self, name: str, value: Any) -> Path:
        return self.write_bytes(name, _json_bytes(value))

    def write_frame(self, name: str, frame: pd.DataFrame) -> Path:
        output = io.BytesIO()
        frame.to_parquet(output, index=False, compression=cfg.PARQUET_COMPRESSION)
        return self.write_bytes(name, output.getvalue())


def observations_frame(
    dates: Any,
    values: Any,
    *,
    extra: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Validate raw observations without interpolation, shifting or imputation."""
    frame = pd.DataFrame(
        {"date": pd.to_datetime(dates, errors="raise"), "value": pd.to_numeric(values)}
    )
    if extra:
        for name, data in extra.items():
            frame[name] = data
    if frame.empty or frame["date"].isna().any():
        raise CollectionError("Empty observations or missing observation dates.")
    present = frame["value"].notna()
    if not present.any() or not np.isfinite(frame.loc[present, "value"]).all():
        raise CollectionError("No finite nonmissing observations.")
    keys = ["date", "realtime_start"] if "realtime_start" in frame else ["date"]
    if frame.duplicated(keys).any():
        raise CollectionError("Duplicate observation keys.")
    return frame.sort_values(keys, kind="stable").reset_index(drop=True)


def parse_fred_records(records: list[dict], *, vintages: bool = False) -> pd.DataFrame:
    raw = pd.DataFrame(records)
    required = {"date", "value"}
    if vintages:
        required |= {"realtime_start", "realtime_end"}
    if not required.issubset(raw.columns):
        raise CollectionError("Unexpected FRED observation schema.")
    values = raw["value"].replace(cfg.FRED_MISSING_VALUE, np.nan)
    extra = None
    if vintages:
        # Keep ISO validity endpoints intact, including the sentinel 9999-12-31.
        # No vintage is substituted with today's value.
        extra = {name: raw[name].astype(str) for name in ("realtime_start", "realtime_end")}
        for column in extra.values():
            if not column.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                raise CollectionError("Invalid ALFRED real-time validity endpoint.")
        if (extra["realtime_start"] > extra["realtime_end"]).any():
            raise CollectionError("Reversed ALFRED validity interval.")
    return observations_frame(raw["date"], values, extra=extra)


def parse_gpr(payload: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(payload), engine="xlrd")
    if not {"month", cfg.GPR_COLUMN}.issubset(raw.columns):
        raise CollectionError("GPR workbook requires month and the reference GPR column.")
    frame = observations_frame(raw["month"], raw[cfg.GPR_COLUMN])
    # The requested reference series starts in 1985, never splice GPRH or GPR_OLD.
    frame = frame.loc[frame["date"] >= pd.Timestamp(cfg.GPR_START_DATE)].reset_index(drop=True)
    if frame.empty:
        raise CollectionError("No observations in the specified GPR reference period.")
    return frame


def parse_epu(payload: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(payload), sheet_name=cfg.EPU_SHEET_NAME, engine="openpyxl")
    required = {"Year", "Month", "News_Based_Policy_Uncert_Index"}
    if not required.issubset(raw.columns):
        raise CollectionError("EPU workbook does not match the US news-based monthly schema.")
    credit = (
        raw["Year"].astype("string").str.startswith(cfg.EPU_CREDIT_PREFIX).fillna(False)
        & raw["Month"].isna()
        & raw["News_Based_Policy_Uncert_Index"].isna()
    )
    credit_count = int(credit.sum())
    # Remove only the explicitly recognized publisher credit, never invalid data.
    raw = raw.loc[~credit].copy()
    dates = pd.to_datetime({"year": raw["Year"], "month": raw["Month"], "day": 1}, errors="raise")
    frame = observations_frame(dates, raw["News_Based_Policy_Uncert_Index"])
    # Do not silently join the separate pre-1985 newspaper methodology.
    frame = frame.loc[frame["date"] >= pd.Timestamp(cfg.EPU_START_DATE)].reset_index(drop=True)
    if frame.empty:
        raise CollectionError("No observations in the specified EPU reference period.")
    frame.attrs["publisher_credit_rows"] = credit_count
    return frame


class Collector:
    def __init__(self, cache: CacheRun, session: requests.Session | None = None):
        self.cache = cache
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": cfg.HTTP_USER_AGENT})
        self.api_key = os.environ.get(cfg.FRED_API_KEY_ENV, "").strip()
        self.artifacts: list[dict[str, Any]] = []

    def _get(
        self, url: str, label: str, suffix: str, params: dict[str, Any] | None = None
    ) -> bytes:
        safe_params = {k: v for k, v in (params or {}).items() if k != "api_key"}
        try:
            response = self.session.get(url, params=params, timeout=cfg.HTTP_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            # requests exception strings can contain the complete URL and API key.
            raise CollectionError(f"{label}: transport error ({type(exc).__name__}).") from None
        if not response.ok:
            raise CollectionError(f"{label}: HTTP {response.status_code}.")
        payload = response.content
        if self.api_key and self.api_key.encode() in payload:
            raise CollectionError(f"{label}: refused a response containing the credential.")
        path = self.cache.write_bytes(f"{label}.{suffix}", payload)
        artifact = {
            "file": path.name,
            "source_url": url,
            "request_parameters": safe_params,
            "downloaded_at_utc": _utc_now().isoformat(),
            "http_status": response.status_code,
            "content_type": response.headers.get("Content-Type", ""),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        self.cache.write_json(f"{label}.metadata.json", artifact)
        self.artifacts.append(artifact)
        return payload

    def _fred_pages(
        self,
        endpoint: str,
        identifier: str,
        collection: str,
        params: dict[str, Any],
        *,
        archive_kind: str = "current",
    ) -> tuple[list[Any], int]:
        if not self.api_key:
            raise CollectionError("FRED_API_KEY missing; ALFRED metadata cannot be measured.")
        items: list[Any] = []
        offset = 0
        total: int | None = None
        while total is None or offset < total:
            query = {
                **params,
                "series_id": identifier,
                "api_key": self.api_key,
                "file_type": "json",
                "offset": offset,
                "sort_order": "asc",
            }
            label = (
                f"{identifier}_{archive_kind}_{endpoint.replace('/', '_')}_{collection}_{offset}"
            )
            payload = self._get(f"{cfg.FRED_API_BASE}/{endpoint}", label, "json", query)
            try:
                document = json.loads(payload)
                batch = document[collection]
                count = int(document["count"])
            except (KeyError, ValueError, TypeError) as exc:
                raise CollectionError(f"{identifier}: invalid FRED pagination/schema.") from exc
            if not isinstance(batch, list) or (total is not None and count != total):
                raise CollectionError(f"{identifier}: FRED dataset changed during pagination.")
            total = count
            if not batch and offset < total:
                raise CollectionError(f"{identifier}: truncated FRED pagination.")
            items.extend(batch)
            offset += len(batch)
            if total == 0:
                break
        if len(items) != total:
            raise CollectionError(f"{identifier}: FRED count mismatch.")
        return items, total

    def fred_current(self, identifier: str) -> pd.DataFrame:
        end = self.cache.downloaded_at.date().isoformat()
        if self.api_key:
            records, _ = self._fred_pages(
                "series/observations",
                identifier,
                "observations",
                {"limit": cfg.FRED_OBSERVATION_LIMIT, "observation_end": end},
            )
            return parse_fred_records(records)
        payload = self._get(cfg.FRED_GRAPH_URL, f"{identifier}_public", "csv", {"id": identifier})
        raw = pd.read_csv(io.BytesIO(payload))
        if identifier not in raw or raw.columns[0] not in {"DATE", "observation_date"}:
            raise CollectionError(f"{identifier}: unexpected public FRED CSV schema.")
        frame = observations_frame(raw.iloc[:, 0], raw[identifier])
        return frame.loc[frame["date"] <= pd.Timestamp(end)].reset_index(drop=True)

    def alfred(self, identifier: str) -> dict[str, Any]:
        end = self.cache.downloaded_at.date().isoformat()
        vintage_dates, count = self._fred_pages(
            "series/vintagedates",
            identifier,
            "vintage_dates",
            {"limit": cfg.FRED_VINTAGE_LIMIT, "realtime_end": end},
            archive_kind="vintages",
        )
        if not vintage_dates or vintage_dates != sorted(set(vintage_dates)):
            raise CollectionError(f"{identifier}: empty or unordered vintage dates.")
        records, record_count = self._fred_pages(
            "series/observations",
            identifier,
            "observations",
            {
                "limit": cfg.FRED_OBSERVATION_LIMIT,
                "realtime_start": cfg.FRED_REALTIME_START,
                "realtime_end": end,
                "observation_end": end,
                "output_type": 1,
            },
            archive_kind="alfred",
        )
        frame = parse_fred_records(records, vintages=True)
        path = self.cache.write_frame(f"{identifier}_alfred.parquet", frame)
        return {
            "vintage_count": count,
            "earliest_vintage": vintage_dates[0],
            "latest_vintage": vintage_dates[-1],
            "vintage_observation_rows": record_count,
            "vintage_file": path.name,
            "vintage_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "alfred_status": "collected",
        }

    def sp500(self, bloomberg_path: Path | None) -> tuple[pd.DataFrame, str, str, str]:
        if bloomberg_path is not None:
            suffix = bloomberg_path.suffix.lower()
            payload = bloomberg_path.read_bytes()
            self.cache.write_bytes("SP500_bloomberg" + suffix, payload)
            if suffix == ".csv":
                raw = pd.read_csv(io.BytesIO(payload))
            elif suffix == ".xlsx":
                raw = pd.read_excel(io.BytesIO(payload), engine="openpyxl")
            elif suffix == ".parquet":
                raw = pd.read_parquet(io.BytesIO(payload))
            else:
                raise CollectionError("Bloomberg input supports csv, xlsx or parquet only.")
            required = {cfg.BLOOMBERG_DATE_COLUMN, cfg.BLOOMBERG_PRICE_COLUMN}
            if not required.issubset(raw.columns):
                raise CollectionError("Bloomberg S&P 500 input requires date and PX_LAST.")
            frame = observations_frame(
                raw[cfg.BLOOMBERG_DATE_COLUMN], raw[cfg.BLOOMBERG_PRICE_COLUMN]
            )
            self.artifacts.append(
                {
                    "file": "SP500_bloomberg" + suffix,
                    "source_url": "local Bloomberg export",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                    "downloaded_at_utc": self.cache.downloaded_at.isoformat(),
                }
            )
            return (
                frame,
                "Bloomberg",
                "local export",
                "Export identity/provenance supplied by user.",
            )
        import yfinance as yf

        try:
            raw = yf.download(
                cfg.YAHOO_SP500_TICKER,
                period=cfg.YAHOO_HISTORY_PERIOD,
                auto_adjust=cfg.YAHOO_AUTO_ADJUST,
                repair=cfg.YAHOO_REPAIR,
                actions=False,
                threads=False,
                progress=False,
                multi_level_index=False,
                timeout=cfg.HTTP_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise CollectionError(
                f"Yahoo S&P 500 transport failed ({type(exc).__name__})."
            ) from None
        if raw.empty or "Close" not in raw:
            raise CollectionError("Yahoo S&P 500 returned no Close history.")
        payload = raw.to_csv(index=True, index_label="Date", lineterminator="\n").encode()
        self.cache.write_bytes("SP500_yfinance_raw.csv", payload)
        source = f"https://finance.yahoo.com/quote/{cfg.YAHOO_SP500_TICKER}/history/"
        self.artifacts.append(
            {
                "file": "SP500_yfinance_raw.csv",
                "source_url": source,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "downloaded_at_utc": _utc_now().isoformat(),
                "library": "yfinance " + version("yfinance"),
                "auto_adjust": cfg.YAHOO_AUTO_ADJUST,
                "archive_kind": "provider dataframe, not original HTTP response",
            }
        )
        dates = raw.index.tz_localize(None).normalize()
        frame = observations_frame(dates, raw["Close"].to_numpy())
        limitation = (
            "Explicit Yahoo fallback: no Bloomberg export supplied. Price-index Close, "
            "auto_adjust=False; downloaded history is not a historical vintage archive."
        )
        return frame, "Yahoo Finance (explicit Bloomberg fallback)", source, limitation

    def collect_one(self, spec: cfg.SeriesSpec, bloomberg_path: Path | None) -> dict[str, Any]:
        row: dict[str, Any] = {
            **asdict(spec),
            "collection_status": "blocked",
            "source_url": "",
            "downloaded_at_utc": self.cache.downloaded_at.isoformat(),
            "first_date": "",
            "last_date": "",
            "n_observations": 0,
            "n_rows_including_missing": 0,
            "missing_observations": 0,
            "vintage_count": None,
            "earliest_vintage": "",
            "latest_vintage": "",
            "vintage_observation_rows": None,
            "vintage_file": "",
            "vintage_file_sha256": "",
            "alfred_status": "not_applicable",
            "availability_applied": False,
            "pit_capability": "not_collected",
            "limitations": "",
            "normalized_file": "",
            "normalized_sha256": "",
            "publisher_credit_rows": 0,
            "pit_rule_requires_decision": spec.identifier in cfg.PUBLICATION_REVIEW,
        }
        identifier = spec.identifier
        try:
            if identifier == "SP500":
                frame, provider, source_url, limitation = self.sp500(bloomberg_path)
                row.update(provider=provider, source_url=source_url, limitations=limitation)
            elif identifier == "GPR":
                payload = self._get(cfg.GPR_URL, "GPR_official", "xls")
                frame = parse_gpr(payload)
                row.update(
                    source_url=cfg.GPR_URL,
                    limitations=(
                        "Reference GPR, 1985 onward only. Current published workbook; "
                        "historical publication timestamps/vintages unavailable in this file. "
                        "SPEC 3.3 uses a 10-day convention, not verified release dates."
                    ),
                )
            elif identifier == "EPU":
                payload = self._get(cfg.EPU_URL, "EPU_official", "xlsx")
                frame = parse_epu(payload)
                row.update(
                    source_url=cfg.EPU_URL,
                    limitations=(
                        "US monthly news index, 1985 onward only, not legacy composite. "
                        "Publisher may revise the previous two months; current workbook "
                        "does not supply historical vintages or release timestamps. "
                        "10-day availability is the SPEC convention, not a verified release."
                    ),
                )
            else:
                frame = self.fred_current(identifier)
                row.update(
                    source_url=f"https://fred.stlouisfed.org/series/{identifier}",
                    limitations=(
                        "Current published observations; actual publication timestamps not "
                        "contained in the raw series. SPEC delay is approximate."
                    ),
                )
            if identifier == "SP500" and frame["value"].dropna().le(0).any():
                raise CollectionError("S&P 500 price index must be strictly positive.")
            path = self.cache.write_frame(f"{identifier}_observations.parquet", frame)
            valid = frame.loc[frame["value"].notna()]
            row.update(
                collection_status="collected",
                first_date=valid["date"].min().strftime(cfg.CSV_DATE_FORMAT),
                last_date=valid["date"].max().strftime(cfg.CSV_DATE_FORMAT),
                n_observations=len(valid),
                n_rows_including_missing=len(frame),
                missing_observations=int(frame["value"].isna().sum()),
                normalized_file=path.name,
                normalized_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                publisher_credit_rows=int(frame.attrs.get("publisher_credit_rows", 0)),
                pit_capability=(
                    "retro_method_delay_convention"
                    if identifier in {"GPR", "EPU"}
                    else "approximate_delay_convention"
                ),
            )
            if spec.use_alfred:
                try:
                    row.update(self.alfred(identifier))
                    row.update(
                        pit_capability="alfred_validity_intervals_collected",
                        limitations=(
                            "ALFRED validity intervals archived; transformations must use "
                            "the vintage in force at each decision, never today's revisions. "
                            "Availability/transformations are not implemented at step 02."
                        ),
                    )
                except (CollectionError, ValueError, OSError) as exc:
                    row.update(
                        collection_status="partial",
                        alfred_status="blocked",
                        pit_status="PIT_APPROXIMATED",
                        limitations=str(exc) + " Only the SPEC fallback delay is available.",
                    )
        except (CollectionError, ValueError, KeyError, OSError, ImportError) as exc:
            message = str(exc)
            if self.api_key:
                message = message.replace(self.api_key, "[REDACTED]")
            row["limitations"] = message
            row["collection_status"] = "partial" if row["normalized_file"] else "blocked"
            if spec.use_alfred and not row["vintage_file"]:
                row["alfred_status"] = "blocked"
                row["pit_status"] = "PIT_APPROXIMATED" if row["normalized_file"] else ""
            elif row["pit_capability"] == "not_collected":
                row["pit_status"] = ""
        if identifier in cfg.PUBLICATION_REVIEW:
            row["limitations"] = (
                row["limitations"] + " " + cfg.PUBLICATION_REVIEW[identifier]
            ).strip()
            if row["normalized_file"]:
                row["pit_capability"] = "publication_delay_requires_validation"
        return row

    def run(self, bloomberg_path: Path | None = None) -> pd.DataFrame:
        # Capture code identity before any network call, not after a long download.
        project = cfg.MODULE_ROOT.parent
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        code_hashes = {
            filename: hashlib.sha256((cfg.MODULE_ROOT / filename).read_bytes()).hexdigest()
            for filename in ("config.py", "collect.py", "requirements.txt")
        }
        rows = []
        for spec in cfg.SERIES:
            row = self.collect_one(spec, bloomberg_path)
            rows.append(row)
            print(
                f"{spec.identifier}: {row['collection_status']} | "
                f"{row['first_date']} .. {row['last_date']} | n={row['n_observations']}",
                flush=True,
            )
        registry = pd.DataFrame(rows)
        for column in ("vintage_count", "vintage_observation_rows"):
            registry[column] = pd.array(registry[column], dtype="Int64")
        registry_payload = registry.to_csv(index=False, lineterminator="\n").encode()
        self.cache.write_bytes(cfg.REGISTRY_FILENAME, registry_payload)
        manifest = {
            "scope": "raw_collection_only_step_02",
            "schema_version": cfg.REGISTRY_SCHEMA_VERSION,
            "downloaded_at_utc": self.cache.downloaded_at.isoformat(),
            "spec_version": cfg.SPEC_VERSION,
            "spec_sha256": cfg.SPEC_SHA256,
            "git_commit": revision.stdout.strip() if revision.returncode == 0 else None,
            "git_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
            "code_sha256": code_hashes,
            "code_changed_during_run": any(
                hashlib.sha256((cfg.MODULE_ROOT / filename).read_bytes()).hexdigest() != digest
                for filename, digest in code_hashes.items()
            ),
            "python": platform.python_version(),
            "packages": {package: version(package) for package in cfg.REQUIREMENT_PACKAGES},
            "artifacts": self.artifacts,
            "source_registry_sha256": hashlib.sha256(registry_payload).hexdigest(),
            "no_forward_returns_computed": True,
            "no_availability_dates_materialized": True,
            "no_portfolio_changes": True,
            "pending_pit_rule_decisions": registry.loc[
                registry["pit_rule_requires_decision"], "identifier"
            ].tolist(),
        }
        self.cache.write_json(cfg.MANIFEST_FILENAME, manifest)
        return registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=cfg.CACHE_ROOT)
    parser.add_argument(
        "--sp500-bloomberg",
        type=Path,
        help="Preferred S&P 500 export, with date and PX_LAST columns; no implicit proxy.",
    )
    args = parser.parse_args()
    cache = CacheRun.create(args.cache_root)
    print(f"Immutable collection directory: {cache.root}", flush=True)
    registry = Collector(cache).run(args.sp500_bloomberg)
    print(f"Source registry: {cache.root / cfg.REGISTRY_FILENAME}", flush=True)
    return int(registry["collection_status"].ne("collected").any())


if __name__ == "__main__":
    raise SystemExit(main())
