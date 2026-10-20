from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.market_metadata import infer_currency

SIGNAL_PATH = Path("data/processed/combined_signal/latest_combined_signal_v1.csv")
UNIVERSE_PATH = Path("data/bloomberg/data/universe.csv")
STATIC_PATH = Path("data/bloomberg/data/static.csv")
FX_PATH = Path("data/bloomberg/data/fx_rates.csv")
YAHOO_MAPPING_PATH = Path("data/bloomberg/data/yahoo_mapping.csv")
CORE_PORTFOLIO_PATH = Path("data/processed/portfolio/portfolio_robust_v1.csv")
ALLOCATION_CONFIG_PATH = Path("config/portfolio_allocation.json")
OUTPUT_DIR = Path("data/processed/opportunistic")


@dataclass(frozen=True)
class OpportunisticConfig:
    core_weight: float = 0.80
    opportunistic_weight: float = 0.20
    opportunistic_positions: int = 4
    max_opportunistic_position_weight: float = 0.05
    max_global_position_weight: float = 0.20
    candidate_pool_size: int = 60
    minimum_history_days: int = 126
    maximum_data_age_days: int = 5
    minimum_average_dollar_volume_usd: float = 5_000_000.0

    def __post_init__(self) -> None:
        if not np.isclose(self.core_weight + self.opportunistic_weight, 1.0):
            raise ValueError("Les poches cœur et opportuniste doivent totaliser 100 %.")
        if self.opportunistic_positions < 1:
            raise ValueError("Il faut au moins une position opportuniste.")
        equal_weight = self.opportunistic_weight / self.opportunistic_positions
        if equal_weight > self.max_opportunistic_position_weight + 1e-12:
            raise ValueError("Le poids opportuniste par titre dépasse le plafond configuré.")
        if self.max_global_position_weight > 0.20:
            raise ValueError("Le plafond global réglementaire est de 20 % par titre.")


def load_config(path: Path = ALLOCATION_CONFIG_PATH) -> OpportunisticConfig:
    return OpportunisticConfig(**json.loads(path.read_text(encoding="utf-8")))


YAHOO_SUFFIXES = {
    "UN": "",
    "US": "",
    "UW": "",
    "UQ": "",
    "UF": "",
    "JT": ".T",
    "KP": ".KS",
    "KQ": ".KQ",
    "HK": ".HK",
    "LN": ".L",
    "FP": ".PA",
    "GY": ".DE",
    "GR": ".DE",
    "NA": ".AS",
    "IM": ".MI",
    "SM": ".MC",
    "SQ": ".MC",
    "SE": ".SW",
    "SS": ".ST",
    "FH": ".HE",
    "C1": ".SS",
    "C2": ".SZ",
    "TT": ".TW",
    "CT": ".TO",
    "IS": ".NS",
    "AT": ".AX",
    "BS": ".SA",
    "SP": ".SI",
    "SJ": ".JO",
    "AB": ".SR",
    "MF": ".MX",
    "DC": ".CO",
    "IT": ".TA",
    "BB": ".BR",
    "ID": ".IR",
    "NO": ".OL",
    "PW": ".WA",
    "MK": ".KL",
    "TB": ".BK",
    "DH": ".AD",
    "GA": ".AT",
    "IJ": ".JK",
    "AV": ".VI",
    "DB": ".DU",
    "KK": ".KW",
    "PL": ".LS",
    "CC": ".SN",
    "NZ": ".NZ",
    "PM": ".PS",
    "HB": ".BD",
    "QD": ".QA",
}


def bloomberg_to_yahoo(ticker_exchange: str) -> str | None:
    parts = str(ticker_exchange).strip().split()
    if len(parts) < 2:
        return None
    ticker = parts[0]
    exchange = parts[-2] if parts[-1].lower() == "equity" else parts[-1]
    if exchange not in YAHOO_SUFFIXES:
        return None
    if exchange == "HK" and ticker.isdigit():
        ticker = ticker.zfill(4)
    if exchange in {"KP", "KQ"} and ticker.isdigit():
        ticker = ticker.zfill(6)
    if exchange == "LN" and ticker.endswith("/"):
        ticker = ticker[:-1]
    else:
        ticker = ticker.replace("/", "-")
    if exchange == "MF":
        ticker = ticker.replace("*", "")
    return ticker + YAHOO_SUFFIXES[exchange]


def _enabled(values: pd.Series) -> pd.Series:
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "oui"})


def load_candidates(
    config: OpportunisticConfig,
    *,
    signal_path: Path = SIGNAL_PATH,
    universe_path: Path = UNIVERSE_PATH,
    mapping_path: Path = YAHOO_MAPPING_PATH,
    static_path: Path = STATIC_PATH,
) -> pd.DataFrame:
    signal = pd.read_csv(signal_path).sort_values("combined_score", ascending=False)
    signal = signal.head(config.candidate_pool_size)
    universe = pd.read_csv(universe_path)[["id", "ticker_exchange", "name"]]
    candidates = signal.merge(universe, on="id", how="left", validate="many_to_one")

    candidates["yahoo_ticker"] = candidates["ticker_exchange"].map(bloomberg_to_yahoo)
    if mapping_path.exists():
        mapping = pd.read_csv(mapping_path)
        if {"id", "yahoo_ticker", "enabled"}.issubset(mapping.columns):
            mapping = mapping[_enabled(mapping["enabled"])].drop_duplicates("id", keep="last")
            overrides = mapping.set_index("id")["yahoo_ticker"]
            candidates["yahoo_ticker"] = (
                candidates["id"].map(overrides).fillna(candidates["yahoo_ticker"])
            )

    if static_path.exists():
        static = pd.read_csv(static_path)
        if {"id", "currency"}.issubset(static.columns):
            currencies = static.drop_duplicates("id", keep="last").set_index("id")["currency"]
            candidates["currency"] = candidates["id"].map(currencies)
    if "currency" not in candidates:
        candidates["currency"] = np.nan
    candidates["currency"] = (
        candidates["currency"]
        .astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
        .fillna(candidates["id"].map(infer_currency))
    )

    candidates["yahoo_ticker"] = candidates["yahoo_ticker"].astype("string").str.strip()
    candidates = candidates.dropna(subset=["yahoo_ticker"])
    candidates = candidates[candidates["yahoo_ticker"].ne("")]
    return candidates.drop_duplicates("yahoo_ticker", keep="first").reset_index(drop=True)


def load_latest_fx(path: Path = FX_PATH) -> pd.Series:
    if not path.exists():
        return pd.Series({"USD": 1.0}, dtype=float)
    fx = pd.read_csv(path, parse_dates=["date"])
    fx["currency"] = fx["currency"].astype(str).str.upper()
    fx["usd_rate"] = pd.to_numeric(fx["usd_rate"], errors="coerce")
    latest = fx.sort_values("date").drop_duplicates("currency", keep="last")
    result = latest.set_index("currency")["usd_rate"].dropna().astype(float)
    result.loc["USD"] = 1.0
    return result


def _extract_field(downloaded: pd.DataFrame, field: str) -> pd.DataFrame:
    if not isinstance(downloaded.columns, pd.MultiIndex):
        if field not in downloaded.columns:
            return pd.DataFrame(index=downloaded.index)
        return downloaded[[field]].copy()
    first = downloaded.columns.get_level_values(0)
    second = downloaded.columns.get_level_values(1)
    if field in first:
        result = downloaded[field].copy()
    elif field in second:
        result = downloaded.xs(field, axis=1, level=1).copy()
    else:
        return pd.DataFrame(index=downloaded.index)
    if isinstance(result, pd.Series):
        result = result.to_frame()
    return result


def download_market_history(
    candidates: pd.DataFrame,
    *,
    period: str = "2y",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError as error:
        message = "Installe les dépendances avec : pip install -r requirements.txt"
        raise RuntimeError(message) from error

    tickers = candidates["yahoo_ticker"].tolist()
    downloaded = yf.download(
        tickers,
        period=period,
        interval="1d",
        auto_adjust=True,
        actions=False,
        repair=True,
        group_by="column",
        progress=False,
        threads=True,
        timeout=20,
        multi_level_index=True,
    )
    if downloaded is None or downloaded.empty:
        raise RuntimeError("Yahoo Finance n'a renvoyé aucune donnée.")

    prices = _extract_field(downloaded, "Close")
    volumes = _extract_field(downloaded, "Volume")
    yahoo_to_id = candidates.set_index("yahoo_ticker")["id"]
    prices = prices.rename(columns=yahoo_to_id).sort_index()
    volumes = volumes.rename(columns=yahoo_to_id).sort_index()
    return prices, volumes


def fetch_analyst_upside(tickers: pd.Series) -> pd.Series:
    try:
        import yfinance as yf
    except ImportError as error:
        message = "Installe les dépendances avec : pip install -r requirements.txt"
        raise RuntimeError(message) from error

    values: dict[str, float] = {}
    for asset, yahoo_ticker in tickers.items():
        try:
            target = yf.Ticker(yahoo_ticker).get_analyst_price_targets()
            current = float(target.get("current", np.nan))
            mean = float(target.get("mean", np.nan))
            values[asset] = mean / current - 1.0 if current > 0 and np.isfinite(mean) else np.nan
        except Exception:
            values[asset] = np.nan
    return pd.Series(values, dtype=float)


def _percentile(values: pd.Series, *, higher_is_better: bool = True) -> pd.Series:
    return values.rank(pct=True, ascending=higher_is_better, method="average")


def _max_drawdown(values: pd.Series) -> float:
    clean = values.dropna()
    if clean.empty:
        return np.nan
    return float((clean / clean.cummax() - 1.0).min())


def _risk_level(volatility: float, drawdown: float) -> str:
    if volatility <= 0.30 and drawdown >= -0.15:
        return "FAIBLE"
    if volatility <= 0.50 and drawdown >= -0.30:
        return "MOYEN"
    return "ELEVE"


def _reason(row: pd.Series) -> str:
    analyst = (
        f", objectif analystes {row['analyst_upside_pct']:+.1%}"
        if np.isfinite(row["analyst_upside_pct"])
        else ", objectif analystes indisponible"
    )
    return (
        f"Momentum 1m {row['momentum_20d']:+.1%}, 3m {row['momentum_60d']:+.1%}; "
        f"volatilité {row['volatility_20d']:.1%}, drawdown 3m {row['max_drawdown_60d']:.1%}; "
        f"liquidité {row['avg_dollar_volume_20d_usd']:,.0f} USD/j{analyst}."
    )


def compute_opportunity_scores(
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    candidates: pd.DataFrame,
    fx_rates: pd.Series,
    config: OpportunisticConfig,
    *,
    analyst_upside: pd.Series | None = None,
    today: pd.Timestamp | None = None,
) -> pd.DataFrame:
    prices = prices.sort_index().apply(pd.to_numeric, errors="coerce")
    volumes = volumes.reindex(index=prices.index, columns=prices.columns).apply(
        pd.to_numeric, errors="coerce"
    )
    returns = prices.pct_change(fill_method=None)
    metadata = candidates.drop_duplicates("id").set_index("id")
    currency = metadata["currency"].astype(str).str.upper().reindex(prices.columns)
    price_to_usd = currency.map(fx_rates)

    last_price = prices.ffill().iloc[-1]
    last_valid_date = prices.apply(lambda series: series.last_valid_index())
    reference_date = pd.Timestamp(today or prices.index.max()).tz_localize(None)
    last_valid_date = pd.to_datetime(last_valid_date).dt.tz_localize(None)
    data_age_days = (reference_date - last_valid_date).dt.days
    observations = prices.notna().sum()
    momentum_20d = last_price / prices.ffill().shift(20).iloc[-1] - 1.0
    momentum_60d = last_price / prices.ffill().shift(60).iloc[-1] - 1.0
    high_252d = prices.tail(252).max()
    distance_252d_high = last_price / high_252d - 1.0
    volatility_20d = returns.tail(20).std(ddof=1) * np.sqrt(252.0)
    downside_60d = returns.tail(60).clip(upper=0.0).pow(2).mean().pow(0.5) * np.sqrt(252.0)
    max_drawdown_60d = prices.tail(60).apply(_max_drawdown)
    avg_traded_value_local = (prices * volumes).tail(20).mean()
    avg_dollar_volume = avg_traded_value_local * price_to_usd

    result = pd.DataFrame(
        {
            "id": prices.columns,
            "last_price": last_price,
            "observations": observations,
            "data_age_days": data_age_days,
            "momentum_20d": momentum_20d,
            "momentum_60d": momentum_60d,
            "distance_252d_high": distance_252d_high,
            "volatility_20d": volatility_20d,
            "downside_deviation_60d": downside_60d,
            "max_drawdown_60d": max_drawdown_60d,
            "avg_dollar_volume_20d_usd": avg_dollar_volume,
        }
    ).reset_index(drop=True)
    metadata_columns = [
        column
        for column in [
            "id",
            "yahoo_ticker",
            "name",
            "currency",
            "combined_score",
            "predicted_excess_return",
        ]
        if column in candidates.columns
    ]
    result = result.merge(candidates[metadata_columns], on="id", how="left", validate="one_to_one")

    result["analyst_upside_pct"] = (
        result["id"].map(analyst_upside) if analyst_upside is not None else np.nan
    )
    result["eligible"] = (
        result["observations"].ge(config.minimum_history_days)
        & result["data_age_days"].le(config.maximum_data_age_days)
        & result["avg_dollar_volume_20d_usd"].ge(config.minimum_average_dollar_volume_usd)
        & result["momentum_20d"].notna()
        & result["momentum_60d"].notna()
        & result["volatility_20d"].gt(0)
    )

    eligible = result["eligible"]
    profit = (
        0.40 * _percentile(result.loc[eligible, "momentum_20d"])
        + 0.20 * _percentile(result.loc[eligible, "momentum_60d"])
        + 0.10 * _percentile(result.loc[eligible, "distance_252d_high"])
        + 0.15 * _percentile(result.loc[eligible, "predicted_excess_return"])
        + 0.15 * _percentile(result.loc[eligible, "analyst_upside_pct"]).fillna(0.50)
    )
    risk = (
        0.45 * _percentile(result.loc[eligible, "volatility_20d"], higher_is_better=False)
        + 0.25 * _percentile(result.loc[eligible, "downside_deviation_60d"], higher_is_better=False)
        + 0.30 * _percentile(result.loc[eligible, "max_drawdown_60d"])
    )
    liquidity = _percentile(result.loc[eligible, "avg_dollar_volume_20d_usd"])
    result.loc[eligible, "profit_score"] = 100.0 * profit
    result.loc[eligible, "risk_score"] = 100.0 * risk
    result.loc[eligible, "liquidity_score"] = 100.0 * liquidity
    result.loc[eligible, "opportunity_score"] = 100.0 * (
        0.55 * profit + 0.30 * risk + 0.15 * liquidity
    )
    result["risk_level"] = [
        _risk_level(volatility, drawdown) if is_eligible else "INELIGIBLE"
        for volatility, drawdown, is_eligible in zip(
            result["volatility_20d"],
            result["max_drawdown_60d"],
            result["eligible"],
            strict=True,
        )
    ]
    result["reason"] = result.apply(_reason, axis=1)
    return result.sort_values("opportunity_score", ascending=False, na_position="last").reset_index(
        drop=True
    )


def build_opportunistic_portfolio(
    scores: pd.DataFrame,
    core_ids: set[str],
    config: OpportunisticConfig,
) -> pd.DataFrame:
    selected = scores[scores["eligible"] & ~scores["id"].isin(core_ids)].head(
        config.opportunistic_positions
    )
    if len(selected) < config.opportunistic_positions:
        raise RuntimeError(
            f"Seulement {len(selected)} candidat(s) éligible(s) hors portefeuille cœur; "
            f"il en faut {config.opportunistic_positions}."
        )
    selected = selected.copy()
    selected["weight"] = config.opportunistic_weight / config.opportunistic_positions
    selected["sleeve"] = "opportunistic"
    return selected


def combine_allocations(
    core: pd.DataFrame,
    opportunistic: pd.DataFrame,
    config: OpportunisticConfig,
) -> pd.DataFrame:
    if not {"id", "weight"}.issubset(core.columns):
        raise ValueError("Le portefeuille cœur doit contenir id et weight.")
    core_allocated = core.copy()
    core_allocated["weight"] = (
        core_allocated["weight"].astype(float) / core_allocated["weight"].sum()
    ) * config.core_weight
    core_allocated["sleeve"] = "core_5w"

    columns = sorted(set(core_allocated.columns).union(opportunistic.columns))
    combined = pd.concat(
        [core_allocated.reindex(columns=columns), opportunistic.reindex(columns=columns)],
        ignore_index=True,
    )
    if combined["id"].duplicated().any():
        raise ValueError("Un titre apparaît dans les deux poches.")
    if not np.isclose(combined["weight"].sum(), 1.0, atol=1e-8):
        raise ValueError("L'allocation combinée ne totalise pas 100 %.")
    if combined["weight"].max() > config.max_global_position_weight + 1e-10:
        raise ValueError("Un titre dépasse le plafond global de 20 %.")
    return combined.sort_values("weight", ascending=False).reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Construit la poche opportuniste de 20 %.")
    parser.add_argument("--skip-analysts", action="store_true")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    candidates = load_candidates(config)
    prices, volumes = download_market_history(candidates, period=args.period)
    fx_rates = load_latest_fx()
    scores = compute_opportunity_scores(prices, volumes, candidates, fx_rates, config)

    if not args.skip_analysts:
        analyst_candidates = scores[scores["eligible"]].head(12).set_index("id")["yahoo_ticker"]
        analyst_upside = fetch_analyst_upside(analyst_candidates)
        scores = compute_opportunity_scores(
            prices,
            volumes,
            candidates,
            fx_rates,
            config,
            analyst_upside=analyst_upside,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.output_dir / "candidate_universe.csv", index=False)
    prices.to_csv(args.output_dir / "yfinance_prices.csv", index_label="date")
    volumes.to_csv(args.output_dir / "yfinance_volumes.csv", index_label="date")
    scores.to_csv(args.output_dir / "opportunity_scores.csv", index=False)

    core = pd.read_csv(CORE_PORTFOLIO_PATH)
    core_ids = set(core.loc[core["weight"].gt(0.005), "id"])
    opportunistic = build_opportunistic_portfolio(scores, core_ids, config)
    combined = combine_allocations(core, opportunistic, config)
    opportunistic.to_csv(args.output_dir / "opportunistic_portfolio.csv", index=False)
    combined.to_csv(args.output_dir / "allocation_80_20.csv", index=False)

    print("\nTOP OPPORTUNITÉS")
    print(
        opportunistic[
            [
                "id",
                "yahoo_ticker",
                "weight",
                "opportunity_score",
                "risk_level",
                "reason",
            ]
        ].to_string(index=False)
    )
    print(f"\nAllocation combinée : {args.output_dir / 'allocation_80_20.csv'}")


if __name__ == "__main__":
    main()
