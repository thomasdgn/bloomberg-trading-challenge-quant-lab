"""D008 schedule and per-query PIT reconstruction; no return calculations."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from macro_engine import config as cfg
from macro_engine.export import csv_bytes
from macro_engine.rebalance_history import compute_history, rebalance_calendar
from macro_engine.run import compute_run


def test_fixed_calendar_four_weeks_holiday_and_final_bound():
    dates = rebalance_calendar()
    assert len(dates) == 78
    assert dates.rebalance_date.iloc[0] == pd.Timestamp("2020-11-06")
    assert dates.rebalance_date.iloc[-1] == pd.Timestamp("2026-10-02")
    assert dates.rebalance_date.diff().dropna().eq(pd.Timedelta(weeks=4)).all()
    holiday = dates.loc[dates.rebalance_date.eq("2021-01-01")].iloc[0]
    assert holiday.query_date == pd.Timestamp("2020-12-31")
    assert dates.query_date.le(dates.rebalance_date).all()
    assert pd.Timestamp("2026-10-16") not in set(dates.rebalance_date)
    with pytest.raises(ValueError, match="Friday"):
        rebalance_calendar("2020-11-05")


def test_historical_query_matches_independent_truncation_and_is_deterministic(reference):
    first = compute_history(reference, start="2020-11-06", end="2020-11-06")
    second = compute_history(
        reference.truncated("2020-11-06"), start="2020-11-06", end="2020-11-06"
    )
    assert_frame_equal(first, second, check_exact=True)
    assert csv_bytes(first) == csv_bytes(second)
    direct = compute_run(reference.truncated("2020-11-06"), "2020-11-06")
    for run in direct:
        part = first[first.ablation.eq(run.ablation)]
        assert (
            part.representative_date.tolist() == run.review_analogues.representative_date.tolist()
        )
        assert part.distance.tolist() == run.review_analogues.distance.tolist()
        assert part.stability_exact.tolist() == run.review_analogues.stability_exact.tolist()
    assert first["sample"].eq("H").all()
    assert first["mode"].eq("strict").all()
    assert not any("return" in name or "performance" in name or name == "ic" for name in first)
    assert first.reference_cache.eq(cfg.REFERENCE_CACHE).all()


def test_missing_query_state_gets_status_not_fabricated_analogues(reference):
    output = compute_history(reference, start="2026-02-20", end="2026-02-20")
    assert len(output) == 2
    assert output["rank"].isna().all()
    assert output.status.eq("INCOMPLETE_QUERY_STATE").all()
    assert output.selected_count.eq(0).all()
