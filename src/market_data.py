"""Prepare dated Bloomberg price exports without implicit currency or gap filling."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MarketDataResult:
    returns_weekly_usd: pd.DataFrame
    benchmark_returns_weekly_usd: pd.Series
    exclusions: dict[str, str]
    dropped_return_dates: list[str]
    current_benchmark_weight_covered: float
    cutoff: str


def _daily_frame(
    frame: pd.DataFrame, name: str, *, cutoff: pd.Timestamp | None = None
) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError(f"{name} must be a nonempty DataFrame.")
    if (
        not isinstance(frame.index, pd.DatetimeIndex)
        or frame.index.tz is not None
        or frame.index.hasnans
        or frame.index.has_duplicates
        or not frame.index.is_monotonic_increasing
        or not frame.index.equals(frame.index.normalize())
        or frame.columns.has_duplicates
    ):
        raise ValueError(f"{name}: require unique, sorted, timezone-naive daily dates/columns.")
    if any(not isinstance(c, str) or not c.strip() for c in frame.columns):
        raise ValueError(f"{name}: identifiers must be nonempty strings.")
    values = (frame if cutoff is None else frame.loc[:cutoff]).astype(float)
    if values.empty:
        raise ValueError(f"{name}: no observations at or before cutoff.")
    if np.isinf(values.to_numpy()).any() or (values <= 0).any().any():
        raise ValueError(f"{name}: observed prices/rates must be finite and positive.")
    return values


def _verified(record: dict, as_of: pd.Timestamp) -> None:
    if not isinstance(record, dict) or record.get("verified") is not True:
        raise ValueError("unverified convention")
    evidence = record.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("missing convention evidence")
    try:
        available = pd.Timestamp(record["available_at"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("missing/invalid available_at") from exc
    if pd.isna(available) or available.tz is not None or available > as_of:
        raise ValueError("convention unavailable at decision time")


def _weekly_endpoints(series: pd.Series, dates: pd.DatetimeIndex, max_age_days: int):
    observed = series.dropna()
    levels = observed.resample("W-FRI").last().reindex(dates)
    timestamps = pd.Series(observed.index, index=observed.index)
    stamps = timestamps.resample("W-FRI").last().reindex(dates)
    ages = (pd.Series(dates, index=dates) - stamps).dt.days
    return levels.where(ages.between(0, max_age_days))


def prepare_market_data(
    prices: pd.DataFrame,
    benchmark: pd.Series,
    universe: pd.DataFrame,
    conventions: dict,
    *,
    as_of: str,
    cutoff: str,
    weeks: int = 52,
    min_observations: int = 40,
    max_age_days: int = 4,
    fx_usd: pd.DataFrame | None = None,
) -> MarketDataResult:
    """Use completed W-FRI periods, exact-date FX, and shared complete returns.

    Asset prices must be split-adjusted PRICE levels, not dividend-reinvested
    levels. FX quotes are USD per major currency unit. Missing rates are never
    carried forward. max_age_days is a calendar-day tolerance, not an exchange
    calendar. Current WLS membership is not historical membership.
    """
    decision, end = pd.Timestamp(as_of), pd.Timestamp(cutoff)
    if (
        pd.isna(decision)
        or pd.isna(end)
        or decision.tz is not None
        or end.tz is not None
        or end != end.normalize()
        or end.dayofweek != 4
        or end >= decision.normalize()
    ):
        raise ValueError("cutoff must be a completed Friday before the decision day.")
    if (
        not isinstance(weeks, int)
        or not isinstance(min_observations, int)
        or not 2 <= min_observations <= weeks
        or not isinstance(max_age_days, int)
        or not 0 <= max_age_days <= 6
    ):
        raise ValueError("Require 2 <= min_observations <= weeks and 0 <= max_age_days <= 6.")
    if not {"id", "index_weight"}.issubset(universe.columns):
        raise ValueError("Universe requires id and index_weight.")
    ids = universe["id"]
    weights = universe["index_weight"].astype(float)
    if (
        ids.isna().any()
        or ids.duplicated().any()
        or any(not isinstance(i, str) or not i.strip() for i in ids)
        or not np.isfinite(weights).all()
        or (weights < 0).any()
        or not np.isclose(weights.sum(), 1, atol=1e-6, rtol=0)
    ):
        raise ValueError("Require unique universe identifiers and full WLS weights summing to 1.")
    if not isinstance(benchmark, pd.Series):
        raise ValueError("benchmark must be a Series of WLS price index levels.")
    if (
        not isinstance(conventions, dict)
        or not isinstance(conventions.get("assets", {}), dict)
        or not isinstance(conventions.get("fx", {}), dict)
    ):
        raise ValueError("Conventions require an object with assets and optional FX objects.")
    prices = _daily_frame(prices, "prices", cutoff=end)
    levels = _daily_frame(benchmark.to_frame("WLS"), "benchmark", cutoff=end)["WLS"]
    fx = _daily_frame(fx_usd, "FX", cutoff=end) if fx_usd is not None else None
    bm = conventions.get("benchmark", {})
    _verified(bm, decision)
    if (
        bm.get("id") != "WLS Index"
        or bm.get("currency") != "USD"
        or bm.get("return_type") != "price"
    ):
        raise ValueError("Require verified USD WLS Index price-return benchmark.")
    dates = pd.date_range(end=end, periods=weeks + 1, freq="W-FRI")
    weekly_bm = _weekly_endpoints(levels, dates, max_age_days)
    if pd.isna(weekly_bm.iloc[-1]):
        raise ValueError("Benchmark endpoint is missing or stale at cutoff.")
    bm_returns = weekly_bm.pct_change(fill_method=None).iloc[1:].rename("WLS Index")
    exclusions, accepted = {}, {}
    members = set(ids)
    for asset in prices.columns:
        if asset not in members:
            exclusions[asset] = "not in supplied WLS universe"
            continue
        record = conventions.get("assets", {}).get(asset, {})
        try:
            _verified(record, decision)
            if record.get("adjustment") != "split_adjusted_price":
                raise ValueError("require split-adjusted price convention")
            multiplier = float(record.get("price_unit_multiplier", np.nan))
            if not np.isfinite(multiplier) or multiplier <= 0:
                raise ValueError("unknown/invalid price unit multiplier")
            currency = record.get("currency")
            if (
                not isinstance(currency, str)
                or len(currency) != 3
                or not currency.isalpha()
                or currency != currency.upper()
            ):
                raise ValueError("unknown/invalid currency")
            usd_prices = prices[asset] * multiplier
            if currency != "USD":
                fx_record = conventions.get("fx", {}).get(currency, {})
                _verified(fx_record, decision)
                if fx_record.get("quote") != "USD_per_unit" or fx is None or currency not in fx:
                    raise ValueError("missing verified USD-per-unit FX series")
                usd_prices = usd_prices * fx[currency].reindex(usd_prices.index)
            if np.isinf(usd_prices.to_numpy()).any() or (usd_prices <= 0).any():
                raise ValueError("invalid normalized USD price")
            weekly = _weekly_endpoints(usd_prices, dates, max_age_days)
            if pd.isna(weekly.iloc[-1]):
                raise ValueError("missing/stale latest price or FX")
            returns = weekly.pct_change(fill_method=None).iloc[1:]
            if returns.notna().sum() < min_observations:
                raise ValueError("insufficient weekly observations")
            accepted[asset] = returns
        except (ValueError, TypeError) as exc:
            exclusions[asset] = str(exc)
    if not accepted:
        raise ValueError(f"No eligible assets. Exclusions: {exclusions}")
    returns = pd.DataFrame(accepted)
    complete = returns.notna().all(axis=1) & bm_returns.notna()
    if complete.sum() < min_observations:
        raise ValueError(
            f"Only {complete.sum()} shared complete weeks; require {min_observations}. "
            "Select an explicit smaller universe; no hidden asset pruning."
        )
    return MarketDataResult(
        returns_weekly_usd=returns.loc[complete],
        benchmark_returns_weekly_usd=bm_returns.loc[complete],
        exclusions=exclusions,
        dropped_return_dates=[str(d.date()) for d in dates[1:][~complete]],
        current_benchmark_weight_covered=float(weights.loc[ids.isin(returns.columns)].sum()),
        cutoff=str(end.date()),
    )
