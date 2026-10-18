"""Section 7 distances, independent episodes and unmodified sensitivities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from threadpoolctl import threadpool_limits

from macro_engine import config as cfg
from macro_engine.normalize import NormalizedState
from macro_engine.pit import calendar

EPISODE_COLUMNS = [
    "sample",
    "mode",
    "query_date",
    "normalization",
    "rank",
    "episode_start",
    "episode_end",
    "representative_date",
    "distance",
    "distance_mahalanobis",
    "closest_variables",
    "farthest_variables",
]


@dataclass(frozen=True)
class AnalogueResult:
    normalized: NormalizedState
    eligible: pd.DataFrame
    episodes: pd.DataFrame
    quantile: float
    separation_months: int
    threshold: float | None

    def fingerprint(self) -> str:
        """Same platform/run parameters produce byte-identical review outputs."""
        metadata = json.dumps(
            {
                "sample": self.normalized.sample,
                "mode": self.normalized.mode,
                "query": str(self.normalized.query_date),
                "method": self.normalized.method,
                "quantile": self.quantile,
                "separation_months": self.separation_months,
                "weights": self.normalized.weights.to_dict(),
            },
            sort_keys=True,
        )
        payload = metadata + self.eligible.to_json(date_format="iso", double_precision=15)
        payload += self.episodes.to_json(date_format="iso", double_precision=15)
        return hashlib.sha256(payload.encode()).hexdigest()


def eligible_distances(normalized: NormalizedState) -> pd.DataFrame:
    """Fit covariance on all complete standardized states <= t, never future."""
    empty = pd.DataFrame(
        columns=["distance", "distance_mahalanobis"],
        index=pd.DatetimeIndex([], name="date"),
        dtype=float,
    )
    if not normalized.ready:
        return empty
    query = normalized.query_date
    history = normalized.values.loc[:query]
    if history.columns.tolist() != normalized.weights.index.tolist():
        raise ValueError("Weights and state spaces do not agree.")
    allowed = (history.index <= query - pd.Timedelta(days=cfg.EMBARGO_CALENDAR_DAYS)) & (
        history.index + pd.Timedelta(weeks=cfg.HORIZON_WEEKS) < query
    )
    candidates = history.loc[allowed]
    if candidates.empty:
        return empty
    differences = candidates.to_numpy() - history.loc[query].to_numpy()
    weighted_square = (differences**2 * normalized.weights.to_numpy()).sum(axis=1)
    # Fix BLAS concurrency, not model parameters, for repeatable covariance sums.
    with threadpool_limits(limits=1):
        precision = LedoitWolf().fit(history.to_numpy()).precision_
        mahalanobis_square = np.einsum("ij,jk,ik->i", differences, precision, differences)
    return pd.DataFrame(
        {
            "distance": np.sqrt(weighted_square),
            "distance_mahalanobis": np.sqrt(np.maximum(mahalanobis_square, 0)),
        },
        index=candidates.index,
    )


def _separated(a: pd.Timestamp, b: pd.Timestamp, months: int) -> bool:
    earlier, later = sorted((a, b))
    return later >= earlier + pd.DateOffset(months=months)


def select_episodes(
    distances: pd.DataFrame, *, quantile: float, separation_months: int
) -> tuple[pd.DataFrame, float | None]:
    """Quantile filter -> NYSE gap clusters -> closest independent episodes."""
    columns = [
        "episode_start",
        "episode_end",
        "representative_date",
        "distance",
        "distance_mahalanobis",
    ]
    if distances.empty:
        return pd.DataFrame(columns=columns), None
    if not distances.index.is_unique or not distances.index.is_monotonic_increasing:
        raise ValueError("Candidate dates must be unique and chronological.")
    threshold = float(distances.distance.quantile(quantile))
    retained = distances.loc[distances.distance < threshold]  # SPEC: under q.
    if retained.empty:
        return pd.DataFrame(columns=columns), threshold
    positions = calendar().get_indexer(retained.index)
    if (positions < 0).any():
        raise ValueError("Non-NYSE candidate.")
    groups = np.cumsum(np.r_[True, np.diff(positions) >= cfg.EPISODE_GAP_SESSIONS])
    records = []
    for _, group in retained.groupby(groups, sort=True):
        # idxmin returns the earliest date in a chronological tie.
        representative = group.distance.idxmin()
        records.append(
            {
                "episode_start": group.index[0],
                "episode_end": group.index[-1],
                "representative_date": representative,
                "distance": float(group.loc[representative, "distance"]),
                "distance_mahalanobis": float(group.loc[representative, "distance_mahalanobis"]),
            }
        )
    ranked = pd.DataFrame(records, columns=columns).sort_values(
        ["distance", "representative_date"], kind="stable"
    )
    chosen = []
    for row in ranked.to_dict("records"):
        if all(
            _separated(
                row["representative_date"], previous["representative_date"], separation_months
            )
            for previous in chosen
        ):
            chosen.append(row)
        if len(chosen) == cfg.ANALOGUE_COUNT:
            break
    return pd.DataFrame(chosen, columns=columns).reset_index(drop=True), threshold


def _find_analogues(
    normalized: NormalizedState,
    *,
    quantile=cfg.DISTANCE_QUANTILE,
    separation_months=cfg.EPISODE_SEPARATION_MONTHS,
    distances: pd.DataFrame,
) -> AnalogueResult:
    if (
        quantile not in cfg.SENSITIVITY_QUANTILES
        or separation_months not in cfg.SENSITIVITY_SEPARATIONS_MONTHS
    ):
        raise ValueError("Only preregistered sensitivity parameters are permitted.")
    chosen, threshold = select_episodes(
        distances, quantile=quantile, separation_months=separation_months
    )
    records = []
    for rank, row in enumerate(chosen.to_dict("records"), 1):
        query = normalized.values.loc[normalized.query_date]
        candidate = normalized.values.loc[row["representative_date"]]
        terms = normalized.weights * (query - candidate) ** 2
        squared_distance = float(terms.sum())
        if squared_distance <= 0:
            raise ValueError("Zero analogue distance: relative contributions are undefined.")
        contributions = terms / squared_distance
        if abs(contributions.sum() - 1) > cfg.CONTRIBUTION_TOLERANCE:
            raise ValueError("Variable contributions do not sum to one.")
        # Stable sorting resolves equal contributions in configured variable order.
        closest = contributions.sort_values(kind="stable").index[:3]
        farthest = contributions.sort_values(ascending=False, kind="stable").index[:3]
        records.append(
            {
                "sample": normalized.sample,
                "mode": normalized.mode,
                "query_date": normalized.query_date,
                "normalization": normalized.method,
                "rank": rank,
                **row,
                "closest_variables": ", ".join(closest),
                "farthest_variables": ", ".join(farthest),
                **{f"contrib_{name}": float(value) for name, value in contributions.items()},
            }
        )
    columns = EPISODE_COLUMNS + [f"contrib_{name}" for name in normalized.weights.index]
    episodes = pd.DataFrame(records, columns=columns)
    return AnalogueResult(
        normalized, distances.copy(), episodes, quantile, separation_months, threshold
    )


def find_analogues(
    normalized: NormalizedState,
    *,
    quantile=cfg.DISTANCE_QUANTILE,
    separation_months=cfg.EPISODE_SEPARATION_MONTHS,
) -> AnalogueResult:
    """Always derive distances from this state's own sample and variable space."""
    return _find_analogues(
        normalized,
        quantile=quantile,
        separation_months=separation_months,
        distances=eligible_distances(normalized),
    )


def sensitivity(normalized: NormalizedState) -> dict[tuple[int, float], AnalogueResult]:
    distances = eligible_distances(normalized)
    return {
        (months, quantile): _find_analogues(
            normalized, quantile=quantile, separation_months=months, distances=distances
        )
        for months, quantile in product(
            cfg.SENSITIVITY_SEPARATIONS_MONTHS, cfg.SENSITIVITY_QUANTILES
        )
    }


def stability_counts(
    base: AnalogueResult, variants: dict[tuple[int, float], AnalogueResult]
) -> pd.DataFrame:
    """No invented stability cutoff: report exact and within-episode counts /9."""
    records = []
    for row in base.episodes.to_dict("records"):
        exact, within = 0, 0
        for variant in variants.values():
            dates = variant.episodes.representative_date
            exact += int(dates.eq(row["representative_date"]).any())
            within += int(((dates >= row["episode_start"]) & (dates <= row["episode_end"])).any())
        records.append(
            {
                "representative_date": row["representative_date"],
                "exact": exact,
                "within_episode": within,
                "variants": len(variants),
            }
        )
    return pd.DataFrame(
        records, columns=["representative_date", "exact", "within_episode", "variants"]
    )


def ablation_fragility(with_news: AnalogueResult, without_news: AnalogueResult) -> pd.Series:
    """Flag a base episode absent from the independently selected ablation.

    Match on episode-interval overlap only, never on an arbitrary extra window.
    Distances in the two variable spaces are not pooled or ranked together.
    """
    flags = []
    for row in with_news.episodes.to_dict("records"):
        other = without_news.episodes
        overlap = (other.episode_start <= row["episode_end"]) & (
            other.episode_end >= row["episode_start"]
        )
        flags.append(not overlap.any())
    return pd.Series(flags, index=with_news.episodes.index, name="fragile_without_news", dtype=bool)
