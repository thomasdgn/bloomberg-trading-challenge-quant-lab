"""Fail-closed input provenance and freshness gate for daily decisions.

Declaring a source 'verified' is a human attestation, never a validation of
Bloomberg entitlements, licenses or the truth of an underlying observation.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from tools.gtc_live.ledger import DataBlocked, age_days

REQUIRED_SOURCES = ("prices", "wls_benchmark", "fx", "wls_membership")


def digest_file(path: str | Path) -> str:
    source = Path(path)
    if not source.is_file():
        raise DataBlocked(f"source file missing: {source}")
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_freshness(
    manifest: dict[str, Any],
    *,
    max_age_days: int = 4,
    file_root: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise DataBlocked("provenance manifest must be an object")
    if not isinstance(max_age_days, int) or max_age_days < 0:
        raise DataBlocked("max_age_days invalid")
    try:
        as_of = date.fromisoformat(str(manifest["as_of_date"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise DataBlocked("as_of_date: valid ISO date required") from exc
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        raise DataBlocked("sources missing")
    statuses = {}
    for key in REQUIRED_SOURCES:
        entry = sources.get(key)
        if not isinstance(entry, dict) or entry.get("verified") is not True:
            raise DataBlocked(f"{key}: source not explicitly verified")
        if not str(entry.get("provenance", "")).strip():
            raise DataBlocked(f"{key}: origin/provenance required")
        age = age_days(entry.get("observed_date"), as_of, key, max_age_days)
        record = {
            "observed_date": entry["observed_date"],
            "age_days": age,
            "provenance": entry["provenance"],
        }
        if "sha256" in entry or "path" in entry:
            if file_root is None or "sha256" not in entry or "path" not in entry:
                raise DataBlocked(f"{key}: both file root and path/hash required")
            root = Path(file_root).resolve()
            file_path = (root / str(entry["path"])).resolve()
            if not file_path.is_relative_to(root):
                raise DataBlocked(f"{key}: file escapes allowed input directory")
            actual = digest_file(file_path)
            if actual.lower() != str(entry["sha256"]).lower():
                raise DataBlocked(f"{key}: source file has changed (SHA256 mismatch)")
            record["sha256"] = actual
        statuses[key] = record
    return {
        "status": "PASS",
        "as_of_date": str(as_of),
        "verified_by_operator_only": True,
        "sources": statuses,
    }
