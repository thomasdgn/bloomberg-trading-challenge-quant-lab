"""Frozen section 3 transformations; all inputs are cut at the decision date."""

import numpy as np
import pandas as pd

from macro_engine import config as cfg
from macro_engine.pit import next_session, sessions


def events_from_series(values: pd.Series, availability, *, retrospective_at=None) -> pd.DataFrame:
    availability = pd.DatetimeIndex(availability)
    return pd.DataFrame(
        {
            "effective_at": availability,
            "value": values.to_numpy(),
            "available_at": availability
            if retrospective_at is None
            else pd.Timestamp(retrospective_at),
        }
    )


def oil_events(observations: pd.DataFrame, end) -> pd.DataFrame:
    end = pd.Timestamp(end)
    raw = (
        observations.loc[observations.date <= end].dropna(subset=["value"]).set_index("date").value
    )
    monthly = raw.groupby(raw.index.to_period("M")).last()
    if monthly.empty:
        return pd.DataFrame(columns=["effective_at", "value", "available_at"])
    # Partial current month is never used as a month-end.
    month_ends = monthly.index.to_timestamp(how="end").normalize()
    availability = next_session(next_session(month_ends))
    monthly = monthly.loc[availability <= end]
    availability = availability[availability <= end]
    if (monthly <= 0).any():
        raise ValueError("Nonpositive WTI month-end price: logarithm forbidden.")
    if monthly.empty:
        return pd.DataFrame(columns=["effective_at", "value", "available_at"])
    full = monthly.reindex(pd.period_range(monthly.index.min(), monthly.index.max(), freq="M"))
    changes = np.log(full / full.shift(cfg.OIL_CHANGE_MONTHS)).reindex(monthly.index)
    return events_from_series(changes, availability)


def regular_events(observations: pd.DataFrame, identifier: str, end) -> pd.DataFrame:
    end = pd.Timestamp(end)
    raw = observations.loc[observations.date <= end].set_index("date").value
    if raw.dropna().empty:
        return pd.DataFrame(columns=["effective_at", "value", "available_at"])
    if identifier == "DCOILWTICO":
        return oil_events(observations, end)
    if identifier in ("GPR", "EPU"):
        available = raw.index.to_period("M").to_timestamp(how="end").normalize() + pd.Timedelta(
            days=cfg.NEWS_PUBLICATION_DELAY_DAYS
        )
        raw, available = raw.loc[available <= end], available[available <= end]
        if (raw.dropna() < 0).any():
            raise ValueError("Negative news index.")
        return events_from_series(np.log1p(raw), available)
    if identifier in ("DGS2", "SP500", "DTWEXBGS"):
        # A stale final observation must not create new rolling/lagged features
        # after its reference date; propagate the last completed feature instead.
        index = sessions(raw.index.min(), min(end, raw.dropna().index.max()))
        # Only carry past levels into missing NYSE observations. No interpolation.
        levels = raw.reindex(raw.index.union(index)).sort_index().ffill().reindex(index)
        if identifier == "DGS2":
            values = levels - levels.shift(cfg.RATE_CHANGE_SESSIONS)
        elif identifier == "SP500":
            if (levels.dropna() <= 0).any():
                raise ValueError("Nonpositive S&P 500 close.")
            values = np.log(levels / levels.shift()).rolling(cfg.VOLATILITY_WINDOW_SESSIONS).std(
                ddof=1
            ) * np.sqrt(cfg.ANNUALIZATION_SESSIONS)
        else:
            if (levels.dropna() <= 0).any():
                raise ValueError("Nonpositive dollar index.")
            values = np.log(levels / levels.shift(cfg.DOLLAR_CHANGE_SESSIONS))
            # D003: descriptive alignment by reference session, no invented J+1
            # publication date. Every value is explicitly retrospective at t.
            return events_from_series(values, index, retrospective_at=end)
        return events_from_series(values, next_session(index))
    if identifier not in ("T10Y2Y", "BAA10Y"):
        raise ValueError(f"Undeclared input series: {identifier}")
    raw = raw.dropna()
    return events_from_series(raw, next_session(raw.index))
