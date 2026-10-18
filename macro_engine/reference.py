"""D006: offline, read-only loading of the one approved reference cache."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from macro_engine import config as cfg


class ReferenceError(RuntimeError):
    """Missing, unapproved or corrupted reference input: fail closed."""


def verified_bytes(path: Path, expected: str) -> bytes:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ReferenceError(f"SHA256 mismatch: {path.name}")
    return payload


def _file(root: Path, name: str) -> Path:
    path = root / name
    if Path(name).name != name or path.resolve().parent != root.resolve():
        raise ReferenceError("Reference path escapes the pinned directory.")
    return path


@dataclass(frozen=True)
class ReferenceData:
    observations: dict[str, pd.DataFrame]
    vintages: dict[str, pd.DataFrame]
    cache_id: str = cfg.REFERENCE_CACHE

    def truncated(self, date: str | pd.Timestamp) -> ReferenceData:
        """In-memory truncation of observation AND publication dates, no writes."""
        end = pd.Timestamp(date).normalize()
        iso = end.strftime("%Y-%m-%d")
        observations = {
            key: frame.loc[frame.date <= end].copy() for key, frame in self.observations.items()
        }
        vintages = {
            key: frame.loc[(frame.date <= end) & (frame.realtime_start <= iso)].copy()
            for key, frame in self.vintages.items()
        }
        return ReferenceData(observations, vintages, self.cache_id)


def load_reference() -> ReferenceData:
    """Verify trust anchors, raw payloads and every input before deserializing.

    No directory argument, cache fallback, network call or write is permitted.
    Deserialize the verified bytes themselves (no check/read race).
    Collection-time code hashes are provenance, not a current-code constraint.
    """
    root = cfg.CACHE_ROOT / cfg.REFERENCE_CACHE
    verified_bytes(cfg.MODULE_ROOT.parent / "SPEC.md", cfg.SPEC_SHA256)
    manifest = json.loads(
        verified_bytes(root / cfg.MANIFEST_FILENAME, cfg.REFERENCE_MANIFEST_SHA256)
    )
    registry = pd.read_csv(
        io.BytesIO(verified_bytes(root / cfg.REGISTRY_FILENAME, cfg.REFERENCE_REGISTRY_SHA256)),
        keep_default_na=False,
    )
    if tuple(registry.identifier) != tuple(series.identifier for series in cfg.SERIES):
        raise ReferenceError("Unexpected reference series registry.")
    for artifact in manifest["artifacts"]:
        verified_bytes(_file(root, artifact["file"]), artifact["sha256"])
    observations, vintages = {}, {}
    for row in registry.to_dict("records"):
        observations[row["identifier"]] = pd.read_parquet(
            io.BytesIO(
                verified_bytes(_file(root, row["normalized_file"]), row["normalized_sha256"])
            )
        )
        if row["vintage_file"]:
            vintages[row["identifier"]] = pd.read_parquet(
                io.BytesIO(
                    verified_bytes(_file(root, row["vintage_file"]), row["vintage_file_sha256"])
                )
            )
    return ReferenceData(observations, vintages)
