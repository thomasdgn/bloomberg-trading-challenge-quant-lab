"""Tests for strict provenance / hash / timestamp gate (synthetic data only)."""
from __future__ import annotations

import hashlib

import pytest

from tools.gtc_live.freshness import REQUIRED_SOURCES, audit_freshness
from tools.gtc_live.ledger import DataBlocked


def manifest() -> dict:
    return {
        "as_of_date": "2026-10-20",
        "sources": {
            name: {
                "verified": True,
                "observed_date": "2026-10-19",
                "provenance": f"manual-confirmation-{name}",
            }
            for name in REQUIRED_SOURCES
        },
    }


def test_current_and_verified_sources_pass() -> None:
    report = audit_freshness(manifest())
    assert report["status"] == "PASS"
    assert set(report["sources"]) == set(REQUIRED_SOURCES)


@pytest.mark.parametrize("break_source", [
    lambda item: item.update(verified=False),
    lambda item: item.update(observed_date="2026-10-07"),
    lambda item: item.update(observed_date="2026-10-21"),
    lambda item: item.update(provenance=""),
])
def test_bad_provenance_or_date_is_blocked(break_source) -> None:
    source = manifest()
    break_source(source["sources"]["wls_benchmark"])
    with pytest.raises(DataBlocked):
        audit_freshness(source)


def test_immutable_hash_verification(tmp_path) -> None:
    source = manifest()
    path = tmp_path / "prices.csv"
    content = b"date,price\n2026-10-20,42\n"
    path.write_bytes(content)
    entry = source["sources"]["prices"]
    entry["path"] = "prices.csv"
    entry["sha256"] = hashlib.sha256(content).hexdigest()
    assert audit_freshness(source, file_root=tmp_path)["status"] == "PASS"
    path.write_bytes(b"tampered")
    with pytest.raises(DataBlocked, match="SHA256"):
        audit_freshness(source, file_root=tmp_path)


def test_path_traversal_is_rejected(tmp_path) -> None:
    source = manifest()
    source["sources"]["fx"].update(path="../secrets", sha256="not-a-real-hash")
    with pytest.raises(DataBlocked, match="escapes"):
        audit_freshness(source, file_root=tmp_path)
