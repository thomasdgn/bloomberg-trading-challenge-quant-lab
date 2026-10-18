"""Availability events, vintage snapshots and forward-only NYSE alignment."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from macro_engine import config as cfg


@lru_cache(maxsize=1)
def calendar() -> pd.DatetimeIndex:
    # A date index only: market observations are never extended into the future.
    return mcal.get_calendar(cfg.CALENDAR).valid_days("1910-01-01", "2030-12-31").tz_localize(None)


def sessions(start, end) -> pd.DatetimeIndex:
    days = calendar()
    return days[(days >= pd.Timestamp(start)) & (days <= pd.Timestamp(end))]


def next_session(dates) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(dates)
    positions = calendar().searchsorted(dates, side="right")
    if (positions == len(calendar())).any():
        raise ValueError("Availability outside supported NYSE calendar.")
    return calendar()[positions]


def propagate(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """As-of join keeps explicit missing values; never interpolate/backfill."""
    if events.empty:
        return pd.DataFrame({"value": np.nan, "available_at": pd.NaT}, index=index)
    ordered = events.sort_values("effective_at", kind="stable").drop_duplicates(
        "effective_at", keep="last"
    )
    return pd.merge_asof(
        pd.DataFrame({"date": index}),
        ordered,
        left_on="date",
        right_on="effective_at",
        direction="backward",
    ).set_index("date")[["value", "available_at"]]


def snapshot(vintages: pd.DataFrame, date) -> pd.DataFrame:
    date = pd.Timestamp(date)
    iso = date.strftime("%Y-%m-%d")
    active = vintages.loc[
        (vintages.realtime_start <= iso) & (vintages.realtime_end >= iso) & (vintages.date <= date)
    ]
    if active.date.duplicated().any():
        raise ValueError("Overlapping ALFRED validity intervals.")
    return active.sort_values("date").copy()


def monthly_value(values: pd.Series, identifier: str) -> pd.Series:
    """Exact calendar-month lag, including missing months; same vintage only."""
    values = values.copy()
    values.index = pd.DatetimeIndex(values.index).to_period("M")
    if values.empty:
        return values
    values = values.reindex(pd.period_range(values.index.min(), values.index.max(), freq="M"))
    if identifier == "CPIAUCNS":
        return 100 * (values / values.shift(cfg.CPI_CHANGE_MONTHS) - 1)
    if identifier == "UNRATE":
        return values - values.shift(cfg.UNEMPLOYMENT_CHANGE_MONTHS)
    raise ValueError("Not an ALFRED monthly transformation.")


def monthly_events(
    vintages: pd.DataFrame, observations: pd.DataFrame, identifier: str, mode: str, end
) -> pd.DataFrame:
    end = pd.Timestamp(end)
    iso = end.strftime("%Y-%m-%d")
    vintages = vintages.loc[(vintages.realtime_start <= iso) & (vintages.date <= end)]
    records = []
    if not vintages.empty and mode == "strict":
        event_dates = set(vintages.realtime_start)
        # Expiry without replacement must also invalidate the old snapshot.
        event_dates.update(
            (pd.Timestamp(value) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            for value in vintages.realtime_end.unique()
            if value < iso
        )
        # Evaluate just the latest reference month and its exact lag in each
        # active vintage. NumPy day dates also support ALFRED's 9999 sentinel.
        starts = np.array(vintages.realtime_start, dtype="datetime64[D]")
        ends = np.array(vintages.realtime_end, dtype="datetime64[D]")
        dates = np.array(vintages.date, dtype="datetime64[D]")
        values = vintages.value.to_numpy(dtype=float)
        lag = cfg.CPI_CHANGE_MONTHS if identifier == "CPIAUCNS" else cfg.UNEMPLOYMENT_CHANGE_MONTHS
        for event in sorted(event_dates):
            day = np.datetime64(event, "D")
            active = (starts <= day) & (ends >= day) & (dates <= day)
            if len(np.unique(dates[active])) != active.sum():
                raise ValueError("Overlapping ALFRED validity intervals.")
            valid = np.flatnonzero(active & np.isfinite(values))
            value = np.nan
            if len(valid):
                latest = valid[np.argmax(dates[valid])]
                lag_date = np.datetime64(
                    pd.Timestamp(dates[latest]) - pd.DateOffset(months=lag), "D"
                )
                previous = np.flatnonzero(active & (dates == lag_date) & np.isfinite(values))
                if len(previous):
                    numerator, denominator = values[latest], values[previous[0]]
                    value = (
                        100 * (numerator / denominator - 1)
                        if identifier == "CPIAUCNS"
                        else numerator - denominator
                    )
            records.append((pd.Timestamp(event), value, pd.Timestamp(event)))
    elif not vintages.empty:
        current = snapshot(vintages, end)
        transformed = monthly_value(current.set_index("date").value, identifier)
        first = vintages.dropna(subset=["value"]).groupby("date").realtime_start.min()
        for period, value in transformed.items():
            observation_date = period.to_timestamp()
            if observation_date not in first:
                continue
            # Historical placement uses first release; revised value is known at t.
            available = pd.Timestamp(first.loc[observation_date])
            records.append((available, value, end))
    else:
        delay = (
            cfg.CPI_FALLBACK_DAYS if identifier == "CPIAUCNS" else cfg.UNEMPLOYMENT_FALLBACK_DAYS
        )
        values = observations.loc[observations.date <= end].set_index("date").value
        for period, value in monthly_value(values, identifier).items():
            available = period.end_time.normalize() + pd.Timedelta(days=delay)
            if available <= end:
                records.append((available, value, available))
    return pd.DataFrame(records, columns=["effective_at", "value", "available_at"])
