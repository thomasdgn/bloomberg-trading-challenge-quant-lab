"""Section 12 analogue invariants and full recomputation under truncation."""

from dataclasses import replace
from itertools import combinations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from sklearn.covariance import LedoitWolf

from macro_engine import config as cfg
from macro_engine.analogues import (
    ablation_fragility,
    find_analogues,
    select_episodes,
    sensitivity,
    stability_counts,
)
from macro_engine.normalize import normalize
from macro_engine.pit import sessions
from macro_engine.state import build_state

COMBINATIONS = (
    ("H", "strict", True),
    ("H", "strict", False),
    ("H", "descriptive", True),
    ("R", "descriptive", True),
)


@pytest.fixture(scope="module")
def actual_results(reference):
    return {
        (sample, mode, news): find_analogues(
            normalize(build_state(reference, cfg.QUERY_DATE, sample, mode, include_news=news))
        )
        for sample, mode, news in COMBINATIONS
    }


@pytest.mark.parametrize("date", cfg.TRUNCATION_TEST_DATES)
@pytest.mark.parametrize("sample,mode,news", COMBINATIONS)
def test_analogue_truncation_including_d007_absence(reference, date, sample, mode, news):
    full = find_analogues(normalize(build_state(reference, date, sample, mode, include_news=news)))
    cut = find_analogues(
        normalize(build_state(reference.truncated(date), date, sample, mode, include_news=news))
    )
    assert_frame_equal(full.normalized.values, cut.normalized.values, check_exact=True)
    assert_frame_equal(full.eligible, cut.eligible, check_exact=True)
    assert_frame_equal(full.episodes, cut.episodes, check_exact=True)
    assert full.fingerprint() == cut.fingerprint()
    if date == "1990-08-15":
        assert full.episodes.empty and cut.episodes.empty
        assert full.eligible.empty and cut.eligible.empty


def test_embargo_and_horizon_on_all_candidates(actual_results):
    for result in actual_results.values():
        dates = result.eligible.index
        assert ((result.normalized.query_date - dates).days >= cfg.EMBARGO_CALENDAR_DAYS).all()
        assert (dates + pd.Timedelta(weeks=cfg.HORIZON_WEEKS) < result.normalized.query_date).all()
        assert pd.Timestamp("2025-10-16") in dates
        assert pd.Timestamp("2025-10-17") not in dates


def test_nyse_gap_exactly_twenty_opens_new_episode():
    index = sessions("1990-01-02", "1993-12-31")
    distances = pd.DataFrame({"distance": 100.0, "distance_mahalanobis": 100.0}, index=index)
    distances.loc[index[[0, 19, 39]], "distance"] = [1.0, 2.0, 0.5]
    selected, _ = select_episodes(distances, quantile=0.05, separation_months=6)
    assert len(selected) == 1
    assert selected.iloc[0].episode_start == index[39]
    assert selected.iloc[0].episode_end == index[39]
    distances.loc[index[39], "distance"] = 100
    distances.loc[index[38], "distance"] = 0.5
    selected, _ = select_episodes(distances, quantile=0.05, separation_months=6)
    assert selected.iloc[0].episode_start == index[0]
    assert selected.iloc[0].episode_end == index[38]


def test_greedy_calendar_separation_ties_and_no_relaxation():
    index = sessions("1990-01-02", "1995-12-29")
    distances = pd.DataFrame({"distance": 100.0, "distance_mahalanobis": 100.0}, index=index)
    dates = pd.to_datetime(["1990-01-02", "1990-07-02", "1991-07-02", "1992-07-02"])
    distances.loc[dates, "distance"] = [1.0, 1.0, 0.5, 0.25]
    selected, _ = select_episodes(distances, quantile=0.05, separation_months=12)
    assert selected.representative_date.tolist() == [dates[3], dates[2], dates[0]]
    assert len(selected) < cfg.ANALOGUE_COUNT


def test_sample_spaces_contributions_and_mahalanobis_independently(actual_results):
    for (sample, mode, news), result in actual_results.items():
        assert result.episodes["sample"].eq(sample).all()
        assert result.episodes["mode"].eq(mode).all()
        assert ("contrib_DTWEXBGS" in result.episodes) == (sample == "R")
        assert not any("DTWEXM" in column for column in result.episodes)
        assert ("contrib_GPR" in result.episodes) == news
        normalized = result.normalized
        precision = LedoitWolf().fit(normalized.values.to_numpy()).precision_
        for row in result.episodes.to_dict("records"):
            difference = (
                normalized.values.loc[normalized.query_date]
                - normalized.values.loc[row["representative_date"]]
            )
            terms = normalized.weights * difference**2
            assert row["distance"] ** 2 == pytest.approx(terms.sum(), abs=1e-12)
            assert row["distance_mahalanobis"] == pytest.approx(
                np.sqrt(difference.to_numpy() @ precision @ difference.to_numpy()), abs=1e-12
            )
            contributions = pd.Series(
                {name: row[f"contrib_{name}"] for name in normalized.weights.index}
            )
            assert contributions.sum() == pytest.approx(1, abs=cfg.CONTRIBUTION_TOLERANCE)
            np.testing.assert_allclose(contributions, terms / terms.sum(), rtol=0, atol=1e-15)
            assert row["closest_variables"] == ", ".join(
                contributions.sort_values(kind="stable").index[:3]
            )
            assert row["farthest_variables"] == ", ".join(
                contributions.sort_values(ascending=False, kind="stable").index[:3]
            )


def test_all_nine_sensitivities_and_representative_separation(actual_results):
    for base in actual_results.values():
        variants = sensitivity(base.normalized)
        assert set(variants) == {(months, q) for months in (6, 12, 24) for q in (0.025, 0.05, 0.10)}
        assert variants[(12, 0.05)].fingerprint() == base.fingerprint()
        for (months, _), result in variants.items():
            assert len(result.episodes) <= 5
            for first, second in combinations(result.episodes.representative_date, 2):
                earlier, later = sorted((first, second))
                assert later >= earlier + pd.DateOffset(months=months)
            for row in result.episodes.to_dict("records"):
                assert (
                    result.eligible.loc[row["representative_date"], "distance"] < result.threshold
                )
        counts = stability_counts(base, variants)
        assert counts.exact.between(1, 9).all()
        assert (counts.within_episode >= counts.exact).all()


def test_determinism_independent_reconstruction(reference, actual_results):
    again = find_analogues(normalize(build_state(reference, cfg.QUERY_DATE)))
    original = actual_results[("H", "strict", True)]
    assert_frame_equal(again.episodes, original.episodes, check_exact=True)
    assert_frame_equal(again.eligible, original.eligible, check_exact=True)
    assert again.fingerprint() == original.fingerprint()


def test_robust_normalization_is_parallel(reference, actual_results):
    for sample, mode, news in COMBINATIONS:
        state = build_state(reference, cfg.QUERY_DATE, sample, mode, include_news=news)
        result = find_analogues(normalize(state, method="robust"))
        assert result.normalized.method == "robust"
        assert result.episodes.normalization.eq("robust").all()
        assert actual_results[(sample, mode, news)].episodes.normalization.eq("standard").all()


def test_invalid_sensitivity_is_not_an_extra_search(actual_results):
    normalized = actual_results[("H", "strict", True)].normalized
    with pytest.raises(ValueError, match="preregistered"):
        find_analogues(normalized, quantile=0.03)
    with pytest.raises(ValueError, match="preregistered"):
        find_analogues(normalized, separation_months=18)


def test_ablation_flag_uses_episode_overlap_not_cross_space_distances(actual_results):
    base = actual_results[("H", "strict", True)]
    without = actual_results[("H", "strict", False)]
    assert ablation_fragility(base, without).tolist() == [False, True, True, False, True]
    empty = replace(without, episodes=without.episodes.iloc[:0])
    assert ablation_fragility(base, empty).all()


def test_normalization_and_covariance_cannot_see_later_states(reference):
    state = build_state(reference, cfg.QUERY_DATE)
    original = find_analogues(normalize(state, "2008-09-15"))
    future = state.values.copy()
    future.loc[future.index > "2008-09-15"] = 1e12
    replay = find_analogues(normalize(replace(state, values=future), "2008-09-15"))
    assert_frame_equal(original.eligible, replay.eligible, check_exact=True)
    assert_frame_equal(original.episodes, replay.episodes, check_exact=True)
