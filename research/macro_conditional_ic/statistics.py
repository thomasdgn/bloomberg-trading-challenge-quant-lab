"""Preregistered statistics; actual partitions only used after the tag guard."""

import numpy as np
from scipy.stats import norm

from research.macro_conditional_ic import config as cfg


def minimum_detectable_effect(n_true: int, n_false: int, sigma: float) -> float | None:
    if min(n_true, n_false) == 0 or not np.isfinite(sigma) or sigma <= 0:
        return None
    critical = norm.ppf(1 - cfg.FAMILY_ALPHA / (2 * cfg.HYPOTHESES)) + norm.ppf(cfg.POWER)
    return float(critical * sigma * np.sqrt(cfg.BLOCK_LENGTH * (1 / n_true + 1 / n_false)))


def conditional_statistics(ic, labels, *, seed: int, n_resamples=cfg.BOOTSTRAP_REPLICATES) -> dict:
    """Paired moving-block bootstrap, preserving missing dates and label runs."""
    ic, labels = np.asarray(ic, dtype=float), np.asarray(labels, dtype=float)
    valid = np.isfinite(ic) & np.isfinite(labels)
    true, false = valid & (labels == 1), valid & (labels == 0)
    n_true, n_false = int(true.sum()), int(false.sum())
    mean_true = float(ic[true].mean()) if n_true else None
    mean_false = float(ic[false].mean()) if n_false else None
    delta = mean_true - mean_false if min(n_true, n_false) else None
    output = {
        "n_true": n_true,
        "n_false": n_false,
        "n_unknown": int((~valid).sum()),
        "ic_true": mean_true,
        "ic_false": mean_false,
        "difference": delta,
        "ci_low": None,
        "ci_high": None,
        "bootstrap_valid": 0,
    }
    n = len(ic)
    if delta is None or n < cfg.BLOCK_LENGTH:
        return output
    rng = np.random.default_rng(seed)
    chunks = []
    blocks = int(np.ceil(n / cfg.BLOCK_LENGTH))
    for start in range(0, n_resamples, cfg.BOOTSTRAP_BATCH):
        size = min(cfg.BOOTSTRAP_BATCH, n_resamples - start)
        starts = rng.integers(0, n - cfg.BLOCK_LENGTH + 1, size=(size, blocks))
        indices = (starts[:, :, None] + np.arange(cfg.BLOCK_LENGTH)).reshape(size, -1)[:, :n]
        observed, flags = ic[indices], labels[indices]
        finite = np.isfinite(observed) & np.isfinite(flags)
        positive, negative = finite & (flags == 1), finite & (flags == 0)
        nt, nf = positive.sum(axis=1), negative.sum(axis=1)
        good = (nt > 0) & (nf > 0)
        boot_true = np.where(positive, observed, 0).sum(axis=1)[good] / nt[good]
        boot_false = np.where(negative, observed, 0).sum(axis=1)[good] / nf[good]
        chunks.append(boot_true - boot_false)
    bootstrap = np.concatenate(chunks)
    output["bootstrap_valid"] = len(bootstrap)
    if len(bootstrap) < cfg.MIN_VALID_BOOTSTRAP_FRACTION * n_resamples:
        return output
    tail = cfg.FAMILY_ALPHA / (2 * cfg.HYPOTHESES)
    low, high = np.quantile(bootstrap, [tail, 1 - tail])
    output["ci_low"] = max(-2.0, float(2 * delta - high))
    output["ci_high"] = min(2.0, float(2 * delta - low))
    return output


def offset_verdict(row: dict) -> str:
    if min(row["n_true"], row["n_false"]) < cfg.MIN_BLOCKS_PER_GROUP or any(
        row[key] is None or not np.isfinite(row[key]) for key in ("ci_low", "ci_high", "mde")
    ):
        return "donnees_insuffisantes"
    if row["ci_low"] > 0 or row["ci_high"] < 0:
        return "effet_detecte"
    if row["ci_low"] > -row["mde"] and row["ci_high"] < row["mde"]:
        return "absence_effet_detectable"
    return "donnees_insuffisantes"


def overall_verdict(rows: list[dict]) -> dict:
    adequate = [
        row
        for row in rows
        if min(row["n_true"], row["n_false"]) >= cfg.MIN_BLOCKS_PER_GROUP
        and row["ci_low"] is not None
        and row["ci_high"] is not None
        and row["mde"] is not None
    ]
    positive = sum(row["difference"] > 0 for row in rows if row["difference"] is not None)
    negative = sum(row["difference"] < 0 for row in rows if row["difference"] is not None)
    verdict = "donnees_insuffisantes"
    if len(adequate) == len(cfg.OFFSETS):
        detected_positive = sum(
            row["verdict"] == "effet_detecte" and row["difference"] > 0 for row in rows
        )
        detected_negative = sum(
            row["verdict"] == "effet_detecte" and row["difference"] < 0 for row in rows
        )
        if max(detected_positive, detected_negative) >= cfg.CONSISTENT_OFFSETS:
            verdict = "effet_detecte"
        elif all(row["verdict"] == "absence_effet_detectable" for row in rows):
            verdict = "absence_effet_detectable"
    return {
        "verdict": verdict,
        "adequate_offsets": len(adequate),
        "positive_offsets": positive,
        "negative_offsets": negative,
    }
