"""Synthetic checks only: no real conditional contrasts before the tag."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from macro_engine import config as macro_cfg
from research.macro_conditional_ic import config as cfg
from research.macro_conditional_ic import infer, prepare
from research.macro_conditional_ic.common import join_labels
from research.macro_conditional_ic.prepare import cross_section_ic, verify_core
from research.macro_conditional_ic.preregister import power_table
from research.macro_conditional_ic.statistics import (
    conditional_statistics,
    minimum_detectable_effect,
    offset_verdict,
    overall_verdict,
)
from src.elastic_net_transversal import FEATURES, TARGET, ElasticNetConfig


def synthetic_labels(dates):
    names = [
        name
        for name, variable, _ in macro_cfg.REGIME_RULES
        if variable in macro_cfg.SAMPLE_VARIABLES["H"]
    ]
    frames = []
    for ablation in cfg.ABLATIONS:
        frame = pd.DataFrame(
            {
                "date": dates,
                "sample": "H",
                "mode": "strict",
                "ablation": ablation,
                "as_of_date": dates.max(),
            }
        )
        for number, name in enumerate(names):
            flags = pd.Series((np.arange(len(dates)) + number) % 3 == 0, dtype="boolean")
            if ablation == "without_news" and name in ("RISQUE_GEO_ELEVE", "INCERTITUDE_ELEVEE"):
                flags[:] = pd.NA
            frame[name] = flags
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def test_strict_join_rejects_same_day_and_keeps_unknown():
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    labels = synthetic_labels(dates)
    labels.loc[labels.date.eq("2020-01-03"), "RALENTISSEMENT"] = pd.NA
    schedule = pd.DataFrame(
        {"date": pd.to_datetime(["2020-01-03", "2020-01-06"]), "offset": [0, 1]}
    )
    joined = join_labels(schedule, labels, "with_news")
    assert joined.macro_date.tolist() == list(dates[:2])
    assert pd.isna(joined.iloc[1].RALENTISSEMENT)
    assert joined.date.gt(joined.macro_date).all()


def test_power_sees_only_global_dispersion_not_conditional_means():
    dates = pd.date_range("2020-01-10", periods=30, freq="W-FRI")
    labels = synthetic_labels(pd.date_range("2020-01-01", dates.max(), freq="B"))
    parts = [
        pd.DataFrame(
            {
                "date": dates,
                "offset": np.arange(30) % 5,
                "score": score,
                "ic": np.sin(np.arange(30)),
            }
        )
        for score in cfg.SCORES
    ]
    ic = pd.concat(parts, ignore_index=True)
    first = power_table(ic, labels)
    shifted = ic.copy()
    shifted["ic"] += 7  # Global shift must not change dispersion or the MDE.
    second = power_table(shifted, labels)
    assert_frame_equal(first, second, rtol=1e-12, atol=1e-12)
    assert len(first) == 200
    assert not {"ic_true", "ic_false", "difference"}.intersection(first.columns)
    assert minimum_detectable_effect(20, 20, 0.2) == pytest.approx(
        2 * minimum_detectable_effect(20, 20, 0.1)
    )
    assert minimum_detectable_effect(40, 40, 0.2) == pytest.approx(
        minimum_detectable_effect(20, 20, 0.2) / np.sqrt(2)
    )
    assert minimum_detectable_effect(0, 20, 0.2) is None


def test_spearman_ties_and_degenerate_scores():
    assert cross_section_ic(
        pd.Series([1.0, 2.0, 3.0, 4.0]), pd.Series([1.0, 1.0, 2.0, 2.0])
    ) == pytest.approx(0.8944271909999159)
    assert np.isnan(cross_section_ic(pd.Series([1.0, 2.0]), pd.Series([1.0, 1.0])))


def test_bootstrap_is_deterministic_paired_and_missing_is_not_false():
    rng = np.random.default_rng(7)
    flags = np.arange(60) % 2
    ic = 0.4 * flags + rng.normal(0, 0.01, size=60)
    first = conditional_statistics(ic, flags, seed=8, n_resamples=2000)
    assert first == conditional_statistics(ic, flags, seed=8, n_resamples=2000)
    assert first["n_true"] == first["n_false"] == 30
    assert first["ci_low"] > 0 and first["ci_high"] > first["ci_low"]
    first["mde"] = minimum_detectable_effect(30, 30, np.std(ic, ddof=1))
    assert offset_verdict(first) == "effet_detecte"
    unknown = flags.astype(float)
    unknown[0] = np.nan
    result = conditional_statistics(ic, unknown, seed=8, n_resamples=2000)
    assert result["n_false"] == 29 and result["n_unknown"] == 1


def test_twenty_block_rule_and_overall_consistency():
    row = {
        "n_true": 20,
        "n_false": 21,
        "ci_low": 0.1,
        "ci_high": 0.3,
        "mde": 0.2,
        "difference": 0.2,
        "verdict": "effet_detecte",
    }
    assert offset_verdict(row) == "effet_detecte"
    assert offset_verdict({**row, "n_true": 19}) == "donnees_insuffisantes"
    assert overall_verdict([row.copy() for _ in range(5)])["verdict"] == "effet_detecte"
    scarce = [row.copy() for _ in range(5)]
    scarce[4]["n_false"] = 19
    assert overall_verdict(scarce)["verdict"] == "donnees_insuffisantes"
    absent = {
        **row,
        "ci_low": -0.02,
        "ci_high": 0.02,
        "difference": 0.0,
        "verdict": "absence_effet_detectable",
    }
    assert offset_verdict(absent) == "absence_effet_detectable"
    assert (
        overall_verdict([absent.copy() for _ in range(5)])["verdict"] == "absence_effet_detectable"
    )
    uncertain = {**row, "ci_low": -0.4, "ci_high": 0.4}
    assert offset_verdict(uncertain) == "donnees_insuffisantes"


def test_inference_tag_guard_precedes_all_real_data_reads(monkeypatch):
    accessed = []

    def denied():
        raise RuntimeError("No preregistered tag")

    monkeypatch.setattr(infer, "guard_preregistered", denied)
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: accessed.append(True))
    with pytest.raises(RuntimeError, match="No preregistered tag"):
        infer.main([])
    assert not accessed


def test_core_is_unchanged_and_synthetic_regeneration_uses_purged_training(monkeypatch):
    assert len(verify_core()) == 4
    model_cfg = replace(ElasticNetConfig(), train_years=1, min_train_rows=20, min_test_rows=5)
    monkeypatch.setattr(prepare, "ElasticNetConfig", lambda: model_cfg)
    rng = np.random.default_rng(12)
    dates = pd.date_range("2010-01-01", periods=70, freq="W-FRI")
    frame = pd.DataFrame(
        [(date, str(stock)) for date in dates for stock in range(10)], columns=["date", "id"]
    )
    for name in FEATURES:
        frame[name] = rng.random(len(frame))
    frame[TARGET] = 0.2 * frame[FEATURES[0]] + rng.normal(0, 0.05, size=len(frame))
    predictions, ic, _ = prepare.regenerate(frame)
    assert not predictions.empty and set(ic.score) == set(cfg.SCORES)
    assert (predictions.train_end_exclusive + pd.Timedelta(weeks=5)).eq(predictions.date).all()
    assert not predictions.duplicated(["date", "id"]).any()
    counts = predictions.groupby("date").combined_score.count()
    assert counts.eq(10).all()
