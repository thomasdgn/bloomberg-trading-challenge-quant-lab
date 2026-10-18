"""Input verification and strict date joining; no conditional means."""

import json
import subprocess

import pandas as pd

from macro_engine import config as macro_cfg
from macro_engine.export import sha256
from research.macro_conditional_ic import config as cfg


def verify_prepared() -> dict:
    manifest = json.loads((cfg.PREPARED / cfg.PREPARED_MANIFEST).read_text())
    for name, digest in manifest["file_sha256"].items():
        if sha256((cfg.PREPARED / name).read_bytes()) != digest:
            raise ValueError(f"Changed prepared file: {name}")
    if (
        manifest["panel_sha256"] != cfg.PANEL_SHA256
        or manifest["target"] != "future_excess_return_5w"
    ):
        raise ValueError("Unapproved panel or target.")
    return manifest


def read_labels() -> pd.DataFrame:
    manifest = json.loads((cfg.LABEL_DIRECTORY / "run_manifest.json").read_text())
    path = cfg.LABEL_DIRECTORY / "macro_regimes.csv"
    if sha256(path.read_bytes()) != manifest["output_sha256"][path.name]:
        raise ValueError("Changed daily labels.")
    if (
        manifest["reference_cache"] != macro_cfg.REFERENCE_CACHE
        or manifest["mode"] != "strict"
        or manifest["sample"] != "H"
    ):
        raise ValueError("Only the approved H strict labels may be used.")
    names = [
        name
        for name, variable, _ in macro_cfg.REGIME_RULES
        if variable in macro_cfg.SAMPLE_VARIABLES["H"]
    ]
    labels = pd.read_csv(path, parse_dates=["date"], dtype=dict.fromkeys(names, "boolean"))
    if not labels["mode"].eq("strict").all() or not labels["sample"].eq("H").all():
        raise ValueError("Mixed modes or samples in labels.")
    return labels


def join_labels(schedule: pd.DataFrame, labels: pd.DataFrame, ablation: str) -> pd.DataFrame:
    """Last macro decision strictly before each nominal prediction date.

    Keep missing flags in the selected row: do not backfill a missing label.
    Across offsets the resulting rows are never treated as independent samples.
    """
    right = (
        labels.loc[labels.ablation.eq(ablation)]
        .drop(columns=["sample", "mode", "ablation", "as_of_date"])
        .rename(columns={"date": "macro_date"})
        .sort_values("macro_date")
    )
    if right.macro_date.duplicated().any():
        raise ValueError("Duplicate macro dates.")
    joined = pd.merge_asof(
        schedule.sort_values("date"),
        right,
        left_on="date",
        right_on="macro_date",
        direction="backward",
        allow_exact_matches=False,
    )
    if joined.macro_date.isna().any() or not joined.date.gt(joined.macro_date).all():
        raise ValueError("Prediction date must be strictly later than macro date.")
    return joined


def guard_preregistered() -> str:
    """No real conditional computation until the exact committed protocol exists."""
    commit = subprocess.check_output(
        ["git", "rev-parse", f"{cfg.TAG}^{{commit}}"], cwd=cfg.ROOT, text=True
    ).strip()
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=cfg.ROOT, check=True)
    frozen_paths = [
        cfg.PROTOCOL,
        cfg.SNAPSHOT,
        cfg.MDE_TABLE,
        *sorted((cfg.ROOT / "research/macro_conditional_ic").glob("*.py")),
    ]
    for path in frozen_paths:
        relative = path.relative_to(cfg.ROOT).as_posix()
        frozen = subprocess.check_output(["git", "show", f"{cfg.TAG}:{relative}"], cwd=cfg.ROOT)
        if frozen.replace(b"\r\n", b"\n") != path.read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"Preregistered file changed: {relative}")
    snapshot = json.loads(cfg.SNAPSHOT.read_text())
    for name, digest in snapshot["prepared_sha256"].items():
        if sha256((cfg.PREPARED / name).read_bytes()) != digest:
            raise ValueError("Prepared data differs from the tagged protocol.")
    label_path = cfg.LABEL_DIRECTORY / "macro_regimes.csv"
    if sha256(label_path.read_bytes()) != snapshot["labels_sha256"]:
        raise ValueError("Labels differ from the tagged protocol.")
    return commit
