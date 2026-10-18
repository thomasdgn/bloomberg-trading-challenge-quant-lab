"""Authorized regeneration of fixed five-week scores; no conditional IC here."""

from __future__ import annotations

import json
import subprocess
import warnings
from dataclasses import asdict

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from threadpoolctl import threadpool_limits

from macro_engine.export import code_provenance, csv_bytes, sha256
from research.macro_conditional_ic import config as cfg
from src.combined_signal_v1 import ELASTIC_WEIGHT, TAIL_WEIGHT
from src.elastic_net_transversal import FEATURES, TARGET, ElasticNetConfig, make_model
from src.tail_model_v1 import make_tail_model, prepare_tail_data
from src.validate_elastic_net import get_test_dates


def verify_core() -> dict:
    hashes = {}
    for name in cfg.CORE_FILES:
        frozen = subprocess.check_output(["git", "show", f"{cfg.CORE_COMMIT}:{name}"], cwd=cfg.ROOT)
        current = (cfg.ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        if current != frozen.replace(b"\r\n", b"\n"):
            raise ValueError(f"Core file differs from the fixed commit: {name}")
        hashes[name] = sha256(frozen)
    return hashes


def cross_section_ic(target, score) -> float:
    valid = target.notna() & score.notna()
    if target.loc[valid].nunique() < 2 or score.loc[valid].nunique() < 2:
        return np.nan
    return float(spearmanr(target.loc[valid], score.loc[valid]).statistic)


def regenerate(panel: pd.DataFrame, *, progress=None):
    model_config = ElasticNetConfig()
    if (
        model_config.purge_weeks != cfg.HORIZON_WEEKS
        or model_config.test_every_n_weeks != cfg.HORIZON_WEEKS
    ):
        raise ValueError("This study exclusively uses the frozen five-week strategy.")
    data = prepare_tail_data(panel)
    schedules = {offset: get_test_dates(data, model_config, offset) for offset in cfg.OFFSETS}
    date_offsets = {date: offset for offset, dates in schedules.items() for date in dates}
    parts, ic_rows, warning_rows = [], [], []
    for number, (date, offset) in enumerate(sorted(date_offsets.items()), 1):
        train_end = date - pd.Timedelta(weeks=model_config.purge_weeks)
        train_start = train_end - pd.DateOffset(years=model_config.train_years)
        train = data.loc[(data.date >= train_start) & (data.date < train_end)]
        test = data.loc[data.date == date].copy()
        if len(train) < model_config.min_train_rows or len(test) < model_config.min_test_rows:
            continue
        elastic, tail = make_model(model_config), make_tail_model()
        with warnings.catch_warnings(record=True) as recorded, threadpool_limits(limits=1):
            warnings.simplefilter("always")
            elastic.fit(train[FEATURES], train[TARGET])
            tail.fit(train[FEATURES], train.tail_target)
            test["predicted_excess_return"] = elastic.predict(test[FEATURES])
            test["tail_probability"] = tail.predict_proba(test[FEATURES])[:, 1]
        warning_rows.extend(
            {
                "date": str(date.date()),
                "type": type(item.message).__name__,
                "message": str(item.message),
            }
            for item in recorded
        )
        test["elastic_rank"] = test.predicted_excess_return.rank(pct=True, method="average")
        test["tail_rank"] = test.tail_probability.rank(pct=True, method="average")
        test["combined_score"] = TAIL_WEIGHT * test.tail_rank + ELASTIC_WEIGHT * test.elastic_rank
        test["offset"], test["train_start"], test["train_end_exclusive"] = (
            offset,
            train_start,
            train_end,
        )
        part = test[
            [
                "date",
                "id",
                "offset",
                TARGET,
                "predicted_excess_return",
                "tail_probability",
                "elastic_rank",
                "tail_rank",
                "combined_score",
                "train_start",
                "train_end_exclusive",
            ]
        ]
        parts.append(part)
        for score in cfg.SCORES:
            ic_rows.append(
                {
                    "date": date,
                    "offset": offset,
                    "score": score,
                    "ic": cross_section_ic(test[TARGET], test[cfg.SCORE_COLUMNS[score]]),
                    "n_stocks": len(test),
                }
            )
        if progress:
            progress(number, len(date_offsets), date)
    return pd.concat(parts, ignore_index=True), pd.DataFrame(ic_rows), warning_rows


def main():
    if cfg.PREPARED.exists():
        raise FileExistsError("Prepared data already exists; no silent overwrite.")
    core_hashes = verify_core()
    payload = cfg.PANEL.read_bytes()
    if sha256(payload) != cfg.PANEL_SHA256:
        raise ValueError("The saved panel hash differs from the approved audit snapshot.")
    panel = pd.read_csv(cfg.PANEL, parse_dates=["date"])

    def progress(number, total, date):
        if number == 1 or number % 10 == 0 or number == total:
            print(
                f"Preparing scores: {number}/{total}, {date.date()} (no conditional IC)", flush=True
            )

    predictions, ic, warning_rows = regenerate(panel, progress=progress)
    cfg.PREPARED.mkdir(parents=True)
    predictions.to_parquet(cfg.PREPARED / cfg.DATA_FILENAME, index=False, compression="zstd")
    (cfg.PREPARED / cfg.IC_FILENAME).write_bytes(csv_bytes(ic))
    # Global reconciliation only; never inspect macro partitions at this stage.
    old = pd.read_csv(cfg.LEGACY_PREDICTIONS, parse_dates=["date"])
    reconciliation = predictions.merge(
        old[["date", "id", "predicted_excess_return"]],
        on=["date", "id"],
        suffixes=("_regenerated", "_saved"),
        validate="one_to_one",
    )
    old_ic = pd.read_csv(cfg.LEGACY_IC_OFFSETS, parse_dates=["date"])
    joined = ic[ic.score.eq("elastic_net")].merge(
        old_ic[["date", "offset", "ic"]],
        on=["date", "offset"],
        suffixes=("_regenerated", "_saved"),
        validate="one_to_one",
    )
    manifest = {
        "authorization": (
            "User authorized regeneration of frozen five-week scores on 2026-10-18, "
            "before conditional results."
        ),
        "core_commit": cfg.CORE_COMMIT,
        "core_file_sha256": core_hashes,
        "panel_sha256": cfg.PANEL_SHA256,
        "target": TARGET,
        "model_config": asdict(ElasticNetConfig()),
        "tail_weight": TAIL_WEIGHT,
        "elastic_weight": ELASTIC_WEIGHT,
        "code": code_provenance(),
        "predictions_rows": len(predictions),
        "ic_rows": len(ic),
        "date_first": str(ic.date.min().date()),
        "date_last": str(ic.date.max().date()),
        "file_sha256": {
            name: sha256((cfg.PREPARED / name).read_bytes())
            for name in (cfg.DATA_FILENAME, cfg.IC_FILENAME)
        },
        "reconciliation": {
            "saved_prediction_pairs": len(reconciliation),
            "max_abs_prediction_difference": float(
                (
                    reconciliation.predicted_excess_return_regenerated
                    - reconciliation.predicted_excess_return_saved
                )
                .abs()
                .max()
            ),
            "saved_ic_pairs": len(joined),
            "max_abs_ic_difference": float((joined.ic_regenerated - joined.ic_saved).abs().max()),
        },
        "warnings": warning_rows,
    }
    (cfg.PREPARED / cfg.PREPARED_MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Prepared {len(predictions)} rows, {len(ic)} unconditional date/score ICs; "
        "no macro partitions examined.",
        flush=True,
    )


if __name__ == "__main__":
    main()
