"""Remaining section 12 label truncation, boundaries and expanding quantiles."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from macro_engine import config as cfg
from macro_engine.analogues import find_analogues
from macro_engine.normalize import normalize
from macro_engine.regimes import label_regimes, regime_thresholds
from macro_engine.state import build_state


@pytest.mark.parametrize("date", cfg.TRUNCATION_TEST_DATES)
@pytest.mark.parametrize(
    "sample,mode,news",
    [
        ("H", "strict", True),
        ("H", "strict", False),
        ("H", "descriptive", True),
        ("R", "descriptive", True),
    ],
)
def test_labels_truncation_including_d007(reference, date, sample, mode, news):
    full = build_state(reference, date, sample, mode, include_news=news)
    cut = build_state(reference.truncated(date), date, sample, mode, include_news=news)
    assert_frame_equal(full.values, cut.values, check_exact=True)
    assert_frame_equal(label_regimes(full), label_regimes(cut), check_exact=True)
    assert_frame_equal(regime_thresholds(full), regime_thresholds(cut), check_exact=True)
    if date == "1990-08-15":
        assert find_analogues(normalize(full)).episodes.empty
        assert find_analogues(normalize(cut)).episodes.empty


def test_quantiles_use_prefix_only_and_strict_boundaries(reference):
    actual = build_state(reference, cfg.QUERY_DATE)
    values = actual.values.iloc[:10].copy()
    for name in values:
        values[name] = np.arange(len(values), dtype=float)
    state = replace(actual, values=values)
    thresholds = regime_thresholds(state)
    for position in range(len(values)):
        for bound, q in zip(("lower", "upper"), cfg.REGIME_PERCENTILES, strict=True):
            assert thresholds.iloc[position][f"CPIAUCNS_{bound}"] == pytest.approx(
                np.quantile(np.arange(position + 1), q)
            )
    labels = label_regimes(state)
    assert not labels.iloc[0].any()  # Exactly equal to a percentile is not above/below.
    assert labels.iloc[-1].INFLATION_HAUTE
    assert labels.iloc[-1].RALENTISSEMENT  # Multiple labels are not exclusive.
    assert labels.iloc[-1].RESSERREMENT
    assert not labels.iloc[-1].INFLATION_BASSE
    future = values.copy()
    future.iloc[5:] = -1e9
    assert_frame_equal(
        labels.iloc[:5], label_regimes(replace(state, values=future)).iloc[:5], check_exact=True
    )


def test_unknown_is_not_false_and_ablation_has_no_news_labels(reference):
    state = build_state(reference, "2026-02-20")
    labels = label_regimes(state)
    assert pd.isna(labels.loc["2026-02-20", "RALENTISSEMENT"])
    assert labels.loc["2026-02-20", "COURBE_INVERSEE"] in (True, False)
    without = label_regimes(build_state(reference, cfg.QUERY_DATE, include_news=False))
    assert "RISQUE_GEO_ELEVE" not in without
    assert "INCERTITUDE_ELEVEE" not in without
    assert "DOLLAR_FORT" not in without
    recent = label_regimes(build_state(reference, cfg.QUERY_DATE, "R", "descriptive"))
    assert "DOLLAR_FORT" in recent


def test_curve_rule_is_strictly_negative(reference):
    state = build_state(reference, cfg.QUERY_DATE)
    values = state.values.iloc[:3].copy()
    values["T10Y2Y"] = [-0.1, 0, 0.1]
    flags = label_regimes(replace(state, values=values)).COURBE_INVERSEE
    assert flags.tolist() == [True, False, False]
