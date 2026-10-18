"""Explicit units, dated input validation, and complete USD weekly histories."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.covariance import estimate_ledoit_wolf


class DataBlocked(ValueError):
    """Missing or ambiguous data: no numerical risk report may be issued."""


@dataclass
class Inputs:
    weights: pd.Series
    benchmark: pd.Series
    covariance: pd.DataFrame
    metadata: pd.DataFrame
    valuation: pd.DataFrame
    provenance: dict
    earnings: pd.DataFrame | None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_portfolio(path):
    path = Path(path)
    portfolio = json.loads(path.read_text(encoding="utf-8"))
    csv_path = None
    if portfolio.get("positions_file"):
        if portfolio.get("positions"):
            raise DataBlocked("Choose inline positions or positions_file, not both.")
        csv_path = Path(portfolio["positions_file"])
        csv_path = csv_path if csv_path.is_absolute() else path.parent / csv_path
        frame = pd.read_csv(csv_path, dtype={"id": str})
        if "id" not in frame:
            raise DataBlocked("Positions CSV requires an id column.")
        portfolio["positions"] = [
            {key: value for key, value in row.items() if pd.notna(value)}
            for row in frame.to_dict("records")
        ]
    return portfolio, csv_path


def daily(frame, name):
    frame = frame.copy()
    frame.index = pd.to_datetime(frame.index, errors="raise")
    if (
        frame.empty
        or frame.index.tz is not None
        or frame.index.has_duplicates
        or frame.index.hasnans
        or not frame.index.equals(frame.index.normalize())
        or frame.columns.has_duplicates
    ):
        raise DataBlocked(f"{name}: require unique daily dates and columns.")
    return frame.sort_index()


def positive_observed(frame, name):
    if np.isinf(frame.to_numpy()).any() or (frame <= 0).any().any():
        raise DataBlocked(f"{name}: nonpositive or infinite observed values.")


def last_value(series, as_of, max_age, name):
    observed = series.loc[:as_of].dropna()
    if observed.empty:
        raise DataBlocked(f"{name}: no value available by {as_of.date()}.")
    date, value = observed.index[-1], float(observed.iloc[-1])
    if not np.isfinite(value) or value <= 0 or (as_of - date).days > max_age:
        raise DataBlocked(f"{name}: invalid or stale value ({date.date()}).")
    return value, date


def weekly(series, endpoints, max_age=4):
    observed = series.dropna()
    levels = observed.resample("W-FRI").last().reindex(endpoints)
    stamps = pd.Series(observed.index, index=observed.index)
    stamps = stamps.resample("W-FRI").last().reindex(endpoints)
    age = (pd.Series(endpoints, index=endpoints) - stamps).dt.days
    return levels.where(age.between(0, max_age))


def portfolio_weights(portfolio, prices, fx, metadata, as_of, max_age):
    if portfolio.get("orders_pending"):
        raise DataBlocked("Pending orders are not executed positions; await execution records.")
    if portfolio.get("status") != "executed":
        raise DataBlocked("Portfolio status must be explicitly 'executed'.")
    positions, cash = portfolio.get("positions", []), portfolio.get("cash", [])
    if not cash:
        raise DataBlocked(
            "Explicit reconciled cash required, including a zero balance if applicable."
        )
    if not positions and not cash:
        raise DataBlocked("An explicit portfolio including cash is required.")
    ids = [row["id"] for row in positions]
    if len(ids) != len(set(ids)) or any(i.startswith("CASH:") for i in ids):
        raise DataBlocked("Duplicate or reserved position identifiers.")
    cash_currencies = [row["currency"] for row in cash]
    if len(cash_currencies) != len(set(cash_currencies)):
        raise DataBlocked("Aggregate cash once per currency.")
    all_rows = positions + cash
    weight_mode = all("weight" in row for row in all_rows)
    if not weight_mode and any("weight" in row for row in all_rows):
        raise DataBlocked("Do not mix weights and monetary/quantity inputs.")
    amounts, valuations = {}, []
    for row in all_rows:
        is_cash = "id" not in row
        asset = f"CASH:{row['currency']}" if is_cash else row["id"]
        if asset not in metadata.index:
            raise DataBlocked(f"Missing metadata: {asset}.")
        currency = metadata.loc[asset, "currency"]
        if row.get("currency", currency) != currency:
            raise DataBlocked(f"Currency mismatch: {asset}.")
        rate, fx_date = (
            (1.0, as_of)
            if currency == "USD"
            else last_value(fx[currency], as_of, max_age, f"FX {currency}")
        )
        value_date, price = None, None
        if weight_mode:
            if set(row) & {"quantity", "market_value", "amount"}:
                raise DataBlocked("A weight cannot also declare an amount or quantity.")
            value = float(row["weight"])
        elif is_cash:
            value = float(row["amount"]) * rate
        elif "quantity" in row and "market_value" not in row:
            price, value_date = last_value(prices[asset], as_of, max_age, asset)
            value = float(row["quantity"]) * price * rate
        elif "market_value" in row and "quantity" not in row:
            if pd.Timestamp(row.get("valuation_date")) != as_of:
                raise DataBlocked("Market value must be dated at the portfolio as-of date.")
            value = float(row["market_value"]) * rate
        else:
            raise DataBlocked(f"{asset}: require quantity, dated market_value, or weight.")
        if not np.isfinite(value) or value < 0:
            raise DataBlocked(f"Invalid long-only holding: {asset}.")
        amounts[asset] = value
        valuations.append(
            {
                "id": asset,
                "input_usd_value_or_weight": value,
                "currency": currency,
                "fx_usd_per_unit": rate,
                "fx_date": str(fx_date.date()),
                "price_date": str(value_date.date()) if value_date is not None else None,
                "price_major_currency": price,
            }
        )
    total = sum(amounts.values())
    if total <= 0 or (weight_mode and not np.isclose(total, 1, atol=1e-8, rtol=0)):
        raise DataBlocked("Positive NAV required; supplied weights must sum to 1 including cash.")
    weights = pd.Series(amounts, dtype=float) / (1 if weight_mode else total)
    return weights, pd.DataFrame(valuations), None if weight_mode else total


def load_inputs(portfolio_path, config_path):
    portfolio_path, config_path = Path(portfolio_path), Path(config_path)
    portfolio, positions_file = read_portfolio(portfolio_path)
    spec = json.loads(config_path.read_text(encoding="utf-8"))
    as_of = pd.Timestamp(portfolio["as_of_date"])
    if pd.isna(as_of) or as_of.tz is not None or as_of != as_of.normalize():
        raise DataBlocked("as_of_date must be a timezone-naive calendar date.")
    if spec.get("conventions_verified") is not True or not spec.get("convention_source"):
        raise DataBlocked("Price units, currencies and return basis need verified source evidence.")
    if spec.get("return_basis") not in ("split_adjusted_price", "total_return"):
        raise DataBlocked("Declare a uniform split_adjusted_price or total_return basis.")
    available = pd.Timestamp(spec.get("available_at"))
    if pd.isna(available) or available > as_of:
        raise DataBlocked("Input conventions were not available by the portfolio date.")
    max_age = int(spec.get("max_valuation_age_days", 7))
    lookback, minimum = int(spec.get("lookback_weeks", 52)), int(spec.get("min_weeks", 40))
    if not 2 <= minimum <= lookback or max_age < 0:
        raise DataBlocked("Invalid history length or valuation freshness limit.")
    paths = {}
    for field in ("prices", "fx", "metadata", "benchmark_weights"):
        path = Path(spec[field])
        paths[field] = path if path.is_absolute() else config_path.parent / path
        if not paths[field].is_file():
            raise DataBlocked(f"Required local source missing: {field}.")
    if portfolio.get("orders_pending") or portfolio.get("status") != "executed":
        raise DataBlocked("Execution not confirmed: pending allocations are not real holdings.")
    meta = pd.read_csv(paths["metadata"], dtype={"id": str}).set_index("id")
    needed = ["currency", "sector", "country", "price_unit_multiplier"]
    if not set(needed).issubset(meta.columns) or meta.index.has_duplicates:
        raise DataBlocked("Metadata require unique ids, currency, sector, country and price units.")
    bm = pd.read_csv(paths["benchmark_weights"], dtype={"id": str}).set_index("id")
    if (
        bm.index.has_duplicates
        or bm.index.hasnans
        or "index_weight" not in bm
        or not np.isfinite(bm.index_weight).all()
        or (bm.index_weight < 0).any()
        or not np.isclose(bm.index_weight.sum(), 1, atol=1e-6, rtol=0)
        or bm.index.str.startswith("CASH:").any()
    ):
        raise DataBlocked("Full WLS weights required, nonnegative and summing to 1; no rescaling.")
    snapshot = pd.Timestamp(spec["benchmark_snapshot_date"])
    if (
        pd.isna(snapshot)
        or snapshot > as_of
        or (as_of - snapshot).days > int(spec.get("max_benchmark_age_days", 7))
    ):
        raise DataBlocked("WLS composition is missing, future-dated or stale.")
    equity_ids = sorted(
        set(bm.index[bm.index_weight > 0]) | {row["id"] for row in portfolio.get("positions", [])}
    )
    missing = set(equity_ids) - set(meta.index)
    if missing:
        raise DataBlocked(f"Missing metadata for {len(missing)} required securities.")
    selected = meta.loc[equity_ids, needed]
    strings = selected[["currency", "sector", "country"]]
    if (
        strings.isna().any().any()
        or strings.astype(str).apply(lambda col: col.str.strip().eq("").any()).any()
    ):
        raise DataBlocked(
            "Incomplete currencies/sectors/countries; no inference from exchange codes."
        )
    if not selected.currency.str.fullmatch(r"[A-Z]{3}").all():
        raise DataBlocked("Currency codes must use uppercase major-currency units.")
    multiplier = pd.to_numeric(selected.price_unit_multiplier, errors="raise")
    if not np.isfinite(multiplier).all() or (multiplier <= 0).any():
        raise DataBlocked("Unknown or invalid price-unit multiplier.")
    prices = daily(pd.read_csv(paths["prices"], index_col="date"), "prices").loc[:as_of]
    missing = set(equity_ids) - set(prices.columns)
    if missing:
        raise DataBlocked(f"Price histories missing for {len(missing)} WLS/held securities.")
    prices = prices[equity_ids].astype(float).mul(multiplier, axis=1)
    positive_observed(prices, "prices")
    quotes = pd.read_csv(paths["fx"])
    if quotes.duplicated(["date", "currency"]).any():
        raise DataBlocked("Duplicate FX observations.")
    fx = daily(quotes.pivot(index="date", columns="currency", values="usd_rate"), "FX")
    fx = fx.loc[:as_of].astype(float)
    positive_observed(fx, "FX")
    cash_currencies = {row["currency"] for row in portfolio.get("cash", [])} | {"USD"}
    currencies = set(selected.currency) | cash_currencies
    missing_fx = currencies - {"USD"} - set(fx.columns)
    if missing_fx:
        raise DataBlocked(f"Missing USD-per-unit FX histories: {sorted(missing_fx)}.")
    for currency in cash_currencies:
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isupper():
            raise DataBlocked("Invalid cash currency.")
        meta.loc[f"CASH:{currency}", ["currency", "sector", "country", "price_unit_multiplier"]] = [
            currency,
            "CASH",
            "CASH_NOT_A_COUNTRY",
            1.0,
        ]
    weights, valuations, nav = portfolio_weights(portfolio, prices, fx, meta, as_of, max_age)
    cutoff = as_of - pd.Timedelta(days=1)
    cutoff -= pd.Timedelta(days=(cutoff.dayofweek - 4) % 7)
    endpoints = pd.date_range(end=cutoff, periods=lookback + 1, freq="W-FRI")
    usd_weekly = {}
    for asset in equity_ids:
        currency = meta.loc[asset, "currency"]
        # Exact observation-date FX; no forward/backward fill or constant spot conversion.
        levels = prices[asset].loc[:cutoff]
        if currency != "USD":
            levels = levels * fx[currency].reindex(levels.index)
        usd_weekly[asset] = weekly(levels, endpoints)
        last_value(prices[asset], as_of, max_age, asset)
        if currency != "USD":
            last_value(fx[currency], as_of, max_age, f"FX {currency}")
    for currency in cash_currencies - {"USD"}:
        usd_weekly[f"CASH:{currency}"] = weekly(fx[currency].loc[:cutoff], endpoints)
    weekly_levels = pd.DataFrame(usd_weekly)
    if weekly_levels.iloc[-1].isna().any():
        raise DataBlocked(
            "Latest completed weekly endpoint is missing/stale for required assets/FX."
        )
    returns = weekly_levels.pct_change(fill_method=None).iloc[1:]
    complete = returns.dropna(how="any")
    if len(complete) < minimum or returns.notna().sum().lt(minimum).any():
        raise DataBlocked(
            f"Only {len(complete)} complete USD weeks; require {minimum}; no pruning."
        )
    if complete.shape[1] < 2:
        raise DataBlocked("The existing Ledoit-Wolf estimator requires at least two risky series.")
    result = estimate_ledoit_wolf(complete, min_observations=minimum)
    if set(result.assets) != set(complete.columns):
        raise DataBlocked("Covariance estimator dropped required assets.")
    ids = sorted(set(complete.columns) | set(weights.index) | {"CASH:USD"})
    weights = weights.reindex(ids, fill_value=0)
    benchmark = bm.index_weight.reindex(ids, fill_value=0)
    # Deterministic USD cash is excluded from shrinkage, then restored with zero covariance.
    covariance = result.covariance_weekly.reindex(index=ids, columns=ids, fill_value=0)
    provenance = {
        "as_of_date": str(as_of.date()),
        "cutoff": str(cutoff.date()),
        "first_return": str(complete.index.min().date()),
        "last_return": str(complete.index.max().date()),
        "n_weeks": result.n_observations,
        "shrinkage": result.shrinkage,
        "missing_weeks_dropped": len(returns) - len(complete),
        "wls_weight_covered": float(benchmark.sum()),
        "nav_usd": nav,
        "cash_convention": "zero local interest; non-USD cash retains historical FX risk",
        "return_basis": spec["return_basis"],
        "benchmark_snapshot_date": str(snapshot.date()),
        "source_sha256": {name: digest(path) for name, path in paths.items()},
        "portfolio_sha256": digest(portfolio_path),
        "config_sha256": digest(config_path),
    }
    if positions_file is not None:
        provenance["positions_file_sha256"] = digest(positions_file)
    earnings = None
    if spec.get("earnings"):
        path = Path(spec["earnings"])
        path = path if path.is_absolute() else config_path.parent / path
        earnings = pd.read_csv(path, parse_dates=["event_date", "available_at"])
        required = {"id", "event_date", "available_at", "source", "status"}
        if not required.issubset(earnings.columns) or earnings[list(required)].isna().any().any():
            raise DataBlocked(
                "Earnings require identified source, event date and availability date."
            )
        provenance["earnings_sha256"] = digest(path)
    return Inputs(
        weights, benchmark, covariance, meta.reindex(ids), valuations, provenance, earnings
    )


def earnings_calendar(inputs, end="2026-11-13"):
    held = inputs.weights.loc[
        ~inputs.weights.index.str.startswith("CASH:") & inputs.weights.gt(0)
    ].nlargest(15)
    as_of, stop = pd.Timestamp(inputs.provenance["as_of_date"]), pd.Timestamp(end)
    rows = []
    for asset, weight in held.items():
        known = pd.DataFrame()
        if inputs.earnings is not None:
            events = inputs.earnings
            known = events.loc[
                events.id.eq(asset)
                & events.available_at.le(as_of)
                & events.event_date.between(as_of, stop)
            ]
        if known.empty:
            rows.append(
                {
                    "id": asset,
                    "weight": weight,
                    "event_date": None,
                    "status": "not_available_in_supplied_data",
                    "source": None,
                }
            )
        else:
            for event in known.sort_values("event_date").itertuples():
                rows.append(
                    {
                        "id": asset,
                        "weight": weight,
                        "event_date": str(event.event_date.date()),
                        "status": event.status,
                        "source": event.source,
                    }
                )
    return pd.DataFrame(rows, columns=["id", "weight", "event_date", "status", "source"])
