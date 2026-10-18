"""Section 8: multiple labels with expanding, current-date-only thresholds."""

import pandas as pd

from macro_engine import config as cfg
from macro_engine.state import DailyState


def regime_thresholds(state: DailyState) -> pd.DataFrame:
    """Each variable uses its nonmissing observations through the row date.

    No 1,260-session filter here: SPEC applies that filter to distances only.
    In descriptive mode these histories retain their explicit query-date vintage.
    """
    columns = {}
    for name, values in state.values.items():
        for bound, q in zip(("lower", "upper"), cfg.REGIME_PERCENTILES, strict=True):
            columns[f"{name}_{bound}"] = values.expanding().quantile(q)
    return pd.DataFrame(columns, index=state.values.index)


def label_regimes(state: DailyState) -> pd.DataFrame:
    thresholds = regime_thresholds(state)
    labels = {}
    for label, name, rule in cfg.REGIME_RULES:
        if name not in state.values:
            continue  # No dollar label in H, no news labels in the ablation.
        values = state.values[name]
        if rule == "negative":
            flags = values < 0
        elif rule == "upper":
            flags = values > thresholds[f"{name}_upper"]
        else:
            flags = values < thresholds[f"{name}_lower"]
        # Unknown is not False, particularly during the UNRATE gap in 2026.
        labels[label] = flags.astype("boolean").mask(values.isna(), pd.NA)
    return pd.DataFrame(labels, index=state.values.index)
