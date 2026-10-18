"""Expanding query-date normalization shared by the query and all candidates."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from macro_engine import config as cfg
from macro_engine.state import DailyState


@dataclass(frozen=True)
class NormalizedState:
    sample: str
    mode: str
    query_date: pd.Timestamp
    method: str
    values: pd.DataFrame
    center: pd.Series
    scale: pd.Series
    weights: pd.Series
    ready: bool


def block_weights(variables) -> pd.Series:
    blocks = {series.identifier: series.block for series in cfg.SERIES}
    if not variables or any(name not in blocks for name in variables):
        raise ValueError("Unknown or empty variable space.")
    counts = pd.Series([blocks[name] for name in variables]).value_counts()
    weights = pd.Series({name: 1 / len(counts) / counts[blocks[name]] for name in variables})
    if abs(weights.sum() - 1) > cfg.WEIGHT_TOLERANCE:
        raise ValueError("Weights do not sum to one.")
    return weights


def normalize(state: DailyState, date=None, *, method="standard") -> NormalizedState:
    query = state.query_date if date is None else pd.Timestamp(date).normalize()
    if query > state.query_date or (state.mode == "descriptive" and query != state.query_date):
        raise ValueError("Rebuild descriptive history at its query date; no future revisions.")
    history = state.values.loc[:query].dropna()
    weights = block_weights(list(history.columns))
    if method == "standard":
        center, scale = history.mean(), history.std(ddof=cfg.STANDARDIZATION_DDOF)
    elif method == "robust":
        center = history.median()
        scale = history.quantile(0.75) - history.quantile(0.25)
    else:
        raise ValueError("Unknown normalization method.")
    ready = len(history) >= cfg.MIN_HISTORY_SESSIONS and query in history.index
    if ready and ((scale <= 0).any() or not np.isfinite(scale).all()):
        raise ValueError("Undefined standardization: nonpositive or nonfinite scale.")
    return NormalizedState(
        state.sample,
        state.mode,
        query,
        method,
        (history - center) / scale,
        center,
        scale,
        weights,
        ready,
    )
