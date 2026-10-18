"""Read-only reference trust boundary; no network is used by these tests."""

from datetime import UTC, datetime

import pytest

from macro_engine import config as cfg
from macro_engine.collect import CacheRun, CollectionError
from macro_engine.reference import ReferenceError, _file, load_reference, verified_bytes


def test_pinned_reference_is_verified_and_complete():
    reference = load_reference()
    assert reference.cache_id == "20261018T143956.868547Z"
    assert set(reference.observations) == set(cfg.SAMPLE_VARIABLES["R"])
    assert set(reference.vintages) == {"CPIAUCNS", "UNRATE"}


def test_hash_failure_is_explicit_and_does_not_repair_or_fetch(tmp_path):
    path = tmp_path / "changed"
    path.write_bytes(b"changed")
    with pytest.raises(ReferenceError, match="SHA256 mismatch"):
        verified_bytes(path, "0" * 64)
    assert path.read_bytes() == b"changed"
    with pytest.raises(ReferenceError, match="escapes"):
        _file(tmp_path, "../outside")


def test_reference_directory_rejects_new_writes():
    cache = CacheRun(cfg.CACHE_ROOT / cfg.REFERENCE_CACHE, datetime.now(UTC))
    with pytest.raises(CollectionError, match="read-only"):
        cache.write_bytes("must_not_exist.txt", b"no write")
    assert not (cache.root / "must_not_exist.txt").exists()
