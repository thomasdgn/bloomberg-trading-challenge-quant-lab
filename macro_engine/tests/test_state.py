"""Section 12 state tests, including actual frozen-input truncation first."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from macro_engine import config as cfg
from macro_engine.normalize import block_weights, normalize
from macro_engine.pit import monthly_events, next_session, propagate, sessions
from macro_engine.state import build_state
from macro_engine.transform import oil_events, regular_events

COMBINATIONS = (("H", "strict"), ("H", "descriptive"), ("R", "descriptive"))


@pytest.mark.parametrize("date", cfg.TRUNCATION_TEST_DATES)
@pytest.mark.parametrize("sample,mode", COMBINATIONS)
def test_state_truncation(reference, date, sample, mode):
    full = build_state(reference, date, sample, mode)
    cut = build_state(reference.truncated(date), date, sample, mode)
    assert_frame_equal(full.values, cut.values, check_exact=True)
    assert_frame_equal(full.available_at, cut.available_at, check_exact=True)
    assert full.statuses == cut.statuses
    a, b = normalize(full), normalize(cut)
    assert_frame_equal(a.values, b.values, check_exact=True)
    assert_series_equal(a.center, b.center, check_exact=True)
    assert_series_equal(a.scale, b.scale, check_exact=True)
    assert a.ready == b.ready
    if date == "1990-08-15":
        assert not a.ready  # D007: identity of absence, never relax 1,260.


def test_zero_availability_violations_entire_strict_history(reference):
    state = build_state(reference, cfg.QUERY_DATE)
    for name in state.values:
        present = state.values[name].notna()
        available = state.available_at.loc[present, name]
        assert available.notna().all()
        assert (available <= available.index).all()
    assert state.statuses["GPR"] == "CONTEMPORARY_INPUT_RETRO_METHOD"
    assert state.statuses["CPIAUCNS"] == "PIT_VERIFIED"


def test_monthly_no_interpolation_between_publications(reference):
    state = build_state(reference, cfg.QUERY_DATE)
    for name in ("CPIAUCNS", "UNRATE", "DCOILWTICO", "GPR", "EPU"):
        for _, group in state.values[name].groupby(state.available_at[name]):
            assert group.dropna().nunique() <= 1
    events = pd.DataFrame(
        {"effective_at": pd.to_datetime(["2020-01-03", "2020-01-10"]), "value": [1.0, 9.0]}
    )
    events["available_at"] = events.effective_at
    aligned = propagate(events, sessions("2020-01-02", "2020-01-13"))
    assert pd.isna(aligned.loc["2020-01-02", "value"])
    assert aligned.loc["2020-01-03":"2020-01-09", "value"].eq(1).all()
    assert aligned.loc["2020-01-10":, "value"].eq(9).all()


def test_alfred_same_vintage_and_no_future_revision():
    dates = pd.to_datetime(["2019-01-01", "2020-01-01", "2019-01-01", "2020-01-01"])
    vintage = pd.DataFrame(
        {
            "date": dates,
            "value": [100.0, 110.0, 200.0, 210.0],
            "realtime_start": ["2020-02-10"] * 2 + ["2020-03-10"] * 2,
            "realtime_end": ["2020-03-09"] * 2 + ["9999-12-31"] * 2,
        }
    )
    raw = pd.DataFrame({"date": dates[:2], "value": [999.0, 888.0]})
    early = monthly_events(vintage, raw, "CPIAUCNS", "strict", "2020-03-02")
    assert early.iloc[-1].value == pytest.approx(10)
    late = monthly_events(vintage, raw, "CPIAUCNS", "strict", "2020-03-11")
    assert late.iloc[-1].value == pytest.approx(5)
    revised = monthly_events(vintage, raw, "CPIAUCNS", "descriptive", "2020-03-11")
    assert revised.iloc[-1].value == pytest.approx(5)
    assert revised.iloc[-1].available_at == pd.Timestamp("2020-03-11")


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_oil_month_end_nonpositive_is_error_but_intramonth_negative_is_valid(bad):
    raw = pd.DataFrame(
        {"date": pd.to_datetime(["2020-04-20", "2020-04-30"]), "value": [-37.0, 19.0]}
    )
    oil_events(raw, "2020-05-05")  # Negative April 20 does not remove April 30.
    raw.loc[1, "value"] = bad
    with pytest.raises(ValueError, match="Nonpositive WTI month-end"):
        oil_events(raw, "2020-05-05")
    oil_events(raw, "2020-04-30")  # Future publication cannot affect an earlier query.


def test_oil_calendar_lag_and_two_business_day_delay():
    dates = pd.date_range("2019-04-30", "2020-04-30", freq="ME")
    raw = pd.DataFrame({"date": dates, "value": np.arange(len(dates)) + 20.0})
    events = oil_events(raw, "2020-05-05")
    assert events.iloc[-1].effective_at == pd.Timestamp("2020-05-04")
    assert events.iloc[-1].value == pytest.approx(np.log(32 / 20))


def test_daily_lags_are_nyse_and_future_close_is_unavailable():
    assert next_session(["2001-09-10"])[0] == pd.Timestamp("2001-09-17")
    raw = pd.DataFrame({"date": pd.to_datetime(["2020-01-02", "2020-01-03"]), "value": [1.0, 99.0]})
    events = regular_events(raw, "BAA10Y", "2020-01-03")
    result = propagate(events, sessions("2020-01-02", "2020-01-03"))
    assert pd.isna(result.iloc[0].value)
    assert result.iloc[-1].value == 1.0


def test_dollar_no_splice_no_invented_publication_and_no_stale_rolling(reference):
    state = build_state(reference, cfg.QUERY_DATE, "R", "descriptive")
    assert "DTWEXM" not in state.values
    assert state.statuses["DTWEXBGS"] == "RETROSPECTIVE"
    assert state.values.loc["2026-10-09":, "DTWEXBGS"].nunique() == 1
    assert state.available_at.DTWEXBGS.eq(pd.Timestamp(cfg.QUERY_DATE)).all()
    with pytest.raises(ValueError, match="D003"):
        build_state(reference, cfg.QUERY_DATE, "R", "strict")


@pytest.mark.parametrize("sample,mode", COMBINATIONS)
@pytest.mark.parametrize("include_news", [True, False])
def test_sample_separation_weights_and_robust_variant(reference, sample, mode, include_news):
    state = build_state(reference, cfg.QUERY_DATE, sample, mode, include_news=include_news)
    normalized = normalize(state)
    assert normalized.sample == sample
    assert ("DTWEXBGS" in normalized.values) == (sample == "R")
    weights = block_weights(list(state.values))
    assert weights.sum() == pytest.approx(1, abs=cfg.WEIGHT_TOLERANCE)
    blocks = {series.identifier: series.block for series in cfg.SERIES}
    totals = weights.groupby(weights.index.map(blocks)).sum()
    assert np.allclose(totals, 1 / len(totals), atol=cfg.WEIGHT_TOLERANCE)
    robust = normalize(state, method="robust")
    assert_series_equal(robust.center, state.complete.median())
    assert_series_equal(robust.scale, state.complete.quantile(0.75) - state.complete.quantile(0.25))
    assert_frame_equal(
        normalized.values, (state.complete - state.complete.mean()) / state.complete.std(ddof=0)
    )


def test_normalization_no_future_and_descriptive_rebuild_required(reference):
    strict = build_state(reference, cfg.QUERY_DATE)
    earlier = normalize(strict, "2008-09-15")
    polluted = strict.values.copy()
    polluted.loc[polluted.index > "2008-09-15"] = 1e9
    replay = normalize(replace(strict, values=polluted), "2008-09-15")
    assert_frame_equal(earlier.values, replay.values, check_exact=True)
    assert earlier.values.index.max() <= pd.Timestamp("2008-09-15")
    with pytest.raises(ValueError, match="Rebuild descriptive"):
        normalize(build_state(reference, cfg.QUERY_DATE, "H", "descriptive"), "2008-09-15")


def test_first_h_strict_distance_is_1260th_complete_session(reference):
    state = build_state(reference, cfg.QUERY_DATE)
    first = state.complete.index[cfg.MIN_HISTORY_SESSIONS - 1]
    assert first == pd.Timestamp("1992-01-27")
    earlier = state.complete.index[cfg.MIN_HISTORY_SESSIONS - 2]
    assert not normalize(state, earlier).ready
    assert normalize(state, first).ready
