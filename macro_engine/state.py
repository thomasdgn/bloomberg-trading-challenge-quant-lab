"""Separate daily spaces; descriptive revisions are rebuilt for each query."""

from dataclasses import dataclass

import pandas as pd

from macro_engine import config as cfg
from macro_engine.pit import monthly_events, propagate, sessions
from macro_engine.reference import ReferenceData
from macro_engine.transform import regular_events


@dataclass(frozen=True)
class DailyState:
    sample: str
    mode: str
    query_date: pd.Timestamp
    values: pd.DataFrame
    available_at: pd.DataFrame
    statuses: dict[str, str]

    @property
    def complete(self) -> pd.DataFrame:
        return self.values.dropna()


def build_state(
    reference: ReferenceData, date, sample="H", mode="strict", *, include_news=True
) -> DailyState:
    if (sample, mode) not in (("H", "strict"), ("H", "descriptive"), ("R", "descriptive")):
        raise ValueError("Only H strict, H descriptive and R descriptive are authorized (D003).")
    end = pd.Timestamp(date).normalize()
    if end not in sessions(end, end):
        raise ValueError("Decision date must be a NYSE session.")
    variables = [
        name for name in cfg.SAMPLE_VARIABLES[sample] if include_news or name not in ("GPR", "EPU")
    ]
    # Include history long enough for lags, then retain complete sample coverage.
    start = max(reference.observations[name].date.min() for name in variables)
    index = sessions(start, end)
    values, availability, statuses = {}, {}, {}
    definitions = {series.identifier: series for series in cfg.SERIES}
    for name in variables:
        if name in ("CPIAUCNS", "UNRATE"):
            vintages = reference.vintages.get(
                name, pd.DataFrame(columns=["date", "value", "realtime_start", "realtime_end"])
            )
            events = monthly_events(vintages, reference.observations[name], name, mode, end)
            status = (
                "PIT_VERIFIED"
                if mode == "strict" and not vintages.empty
                else "RETROSPECTIVE"
                if mode == "descriptive"
                else "PIT_APPROXIMATED"
            )
        else:
            events = regular_events(reference.observations[name], name, end)
            status = "RETROSPECTIVE" if name == "DTWEXBGS" else definitions[name].pit_status
        aligned = propagate(events.loc[events.effective_at <= end], index)
        values[name], availability[name], statuses[name] = (
            aligned.value,
            aligned.available_at,
            status,
        )
    frame, dates = pd.DataFrame(values, index=index), pd.DataFrame(availability, index=index)
    complete = frame.dropna()
    if not complete.empty:
        frame, dates = frame.loc[complete.index[0] :], dates.loc[complete.index[0] :]
    else:
        # No sample exists yet. Its representation must not depend on future
        # source coverage (notably R before the dollar series begins).
        frame, dates = frame.iloc[:0], dates.iloc[:0]
    frame.index.name = dates.index.name = "date"
    return DailyState(sample, mode, end, frame, dates, statuses)
