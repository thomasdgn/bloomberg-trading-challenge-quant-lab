from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.opportunistic_model import _extract_field, bloomberg_to_yahoo

PRICES_PATH = Path("data/bloomberg/data/prices_10y.csv.gz")
VOLUMES_PATH = Path("data/bloomberg/data/volumes_10y.csv.gz")
UNIVERSE_PATH = Path("data/bloomberg/data/universe.csv")
YAHOO_MAPPING_PATH = Path("data/bloomberg/data/yahoo_mapping.csv")
REPORT_PATH = Path("data/processed/data_refresh/yahoo_feature_refresh.csv")


@dataclass(frozen=True)
class RefreshConfig:
    overlap_days: int = 10
    maximum_median_relative_error: float = 0.02
    minimum_overlap_observations: int = 1
    batch_size: int = 100


def _enabled(values: pd.Series) -> pd.Series:
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "oui"})


def load_yahoo_mapping(
    history_assets: pd.Index,
    *,
    universe_path: Path = UNIVERSE_PATH,
    override_path: Path = YAHOO_MAPPING_PATH,
) -> pd.DataFrame:
    universe = pd.read_csv(universe_path, usecols=["id", "ticker_exchange"])
    universe = universe.drop_duplicates("id", keep="last").set_index("id")
    mapping = pd.DataFrame({"id": history_assets.astype(str)})
    mapping["ticker_exchange"] = mapping["id"].map(universe["ticker_exchange"])
    mapping["yahoo_ticker"] = mapping["ticker_exchange"].map(bloomberg_to_yahoo)

    if override_path.exists():
        overrides = pd.read_csv(override_path)
        required = {"id", "yahoo_ticker", "enabled"}
        if required.issubset(overrides.columns):
            overrides = overrides[_enabled(overrides["enabled"])].drop_duplicates("id", keep="last")
            override_values = overrides.set_index("id")["yahoo_ticker"]
            mapping["yahoo_ticker"] = (
                mapping["id"].map(override_values).fillna(mapping["yahoo_ticker"])
            )

    mapping["yahoo_ticker"] = mapping["yahoo_ticker"].astype("string").str.strip()
    mapping.loc[mapping["yahoo_ticker"].eq(""), "yahoo_ticker"] = pd.NA
    duplicate = mapping["yahoo_ticker"].notna() & mapping["yahoo_ticker"].duplicated(False)
    mapping["mapping_status"] = np.select(
        [mapping["yahoo_ticker"].isna(), duplicate],
        ["NO_MAPPING", "DUPLICATE_YAHOO_TICKER"],
        default="READY",
    )
    return mapping


def download_yahoo_history(
    mapping: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    batch_size: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError as error:
        raise RuntimeError(
            "Installe les dépendances avec : pip install -r requirements.txt"
        ) from error

    ready = mapping[mapping["mapping_status"].eq("READY")]
    yahoo_to_id = ready.set_index("yahoo_ticker")["id"]
    tickers = yahoo_to_id.index.tolist()
    price_parts: list[pd.DataFrame] = []
    volume_parts: list[pd.DataFrame] = []
    exclusive_end = end + pd.Timedelta(days=1)

    for offset in range(0, len(tickers), batch_size):
        batch = tickers[offset : offset + batch_size]
        print(
            f"Téléchargement Yahoo {offset + 1}-{min(offset + batch_size, len(tickers))} "
            f"sur {len(tickers)}"
        )
        downloaded = yf.download(
            batch,
            start=start.date().isoformat(),
            end=exclusive_end.date().isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=False,
            repair=True,
            group_by="column",
            progress=False,
            threads=True,
            timeout=30,
            multi_level_index=True,
        )
        if downloaded is None or downloaded.empty:
            continue
        prices = _extract_field(downloaded, "Close").rename(columns=yahoo_to_id)
        volumes = _extract_field(downloaded, "Volume").rename(columns=yahoo_to_id)
        price_parts.append(prices)
        volume_parts.append(volumes)

    if not price_parts:
        raise RuntimeError("Yahoo Finance n'a renvoyé aucune donnée.")

    prices = pd.concat(price_parts, axis=1, sort=False).sort_index()
    volumes = pd.concat(volume_parts, axis=1, sort=False).sort_index()
    prices = prices.loc[:, ~prices.columns.duplicated()].apply(pd.to_numeric, errors="coerce")
    volumes = volumes.loc[:, ~volumes.columns.duplicated()].apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    volumes.index = pd.to_datetime(volumes.index).tz_localize(None)
    return prices, volumes


def validate_download(
    existing_prices: pd.DataFrame,
    downloaded_prices: pd.DataFrame,
    mapping: pd.DataFrame,
    *,
    last_source_date: pd.Timestamp,
    config: RefreshConfig,
) -> pd.DataFrame:
    report = mapping.copy()
    report["overlap_observations"] = 0
    report["median_relative_error"] = np.nan
    report["new_price_observations"] = 0
    report["new_volume_observations"] = 0
    report["latest_download_date"] = pd.NaT
    report["refresh_status"] = report["mapping_status"]

    for index, row in report[report["mapping_status"].eq("READY")].iterrows():
        asset = row["id"]
        if asset not in downloaded_prices:
            report.loc[index, "refresh_status"] = "NO_DOWNLOAD"
            continue

        existing = existing_prices[asset].dropna()
        downloaded = downloaded_prices[asset].dropna()
        common_dates = existing.index.intersection(downloaded.index)
        if len(common_dates):
            relative_errors = (
                downloaded.loc[common_dates].sub(existing.loc[common_dates]).abs()
                / existing.loc[common_dates].abs().replace(0.0, np.nan)
            ).dropna()
        else:
            relative_errors = pd.Series(dtype=float)

        overlap_count = int(len(relative_errors))
        median_error = float(relative_errors.median()) if overlap_count else np.nan
        new_count = int((downloaded.index > last_source_date).sum())
        report.loc[index, "overlap_observations"] = overlap_count
        report.loc[index, "median_relative_error"] = median_error
        report.loc[index, "new_price_observations"] = new_count
        report.loc[index, "latest_download_date"] = downloaded.index.max()

        if overlap_count < config.minimum_overlap_observations:
            report.loc[index, "refresh_status"] = "NO_OVERLAP"
        elif median_error > config.maximum_median_relative_error:
            report.loc[index, "refresh_status"] = "OVERLAP_MISMATCH"
        elif new_count == 0:
            report.loc[index, "refresh_status"] = "NO_NEW_OBSERVATION"
        else:
            report.loc[index, "refresh_status"] = "VALIDATED"

    return report


def merge_validated_history(
    existing: pd.DataFrame,
    downloaded: pd.DataFrame,
    report: pd.DataFrame,
    *,
    last_source_date: pd.Timestamp,
) -> pd.DataFrame:
    valid_assets = report.loc[report["refresh_status"].eq("VALIDATED"), "id"].tolist()
    new_values = downloaded.loc[downloaded.index > last_source_date, valid_assets]
    combined = existing.reindex(existing.index.union(new_values.index).sort_values())
    combined.loc[new_values.index, valid_assets] = new_values
    combined.index.name = "date"
    return combined


def refresh_market_data(
    *,
    end: pd.Timestamp,
    config: RefreshConfig | None = None,
    prices_path: Path = PRICES_PATH,
    volumes_path: Path = VOLUMES_PATH,
    universe_path: Path = UNIVERSE_PATH,
    mapping_path: Path = YAHOO_MAPPING_PATH,
    report_path: Path = REPORT_PATH,
) -> pd.DataFrame:
    cfg = config or RefreshConfig()
    prices = pd.read_csv(prices_path, index_col="date", parse_dates=True).sort_index()
    volumes = pd.read_csv(volumes_path, index_col="date", parse_dates=True).sort_index()
    if not prices.index.equals(volumes.index) or not prices.columns.equals(volumes.columns):
        raise ValueError("Les historiques de prix et volumes ne sont pas alignés.")

    last_source_date = pd.Timestamp(prices.index.max())
    end = pd.Timestamp(end).normalize()
    if end <= last_source_date:
        print(
            f"Historique déjà présent jusqu'au {last_source_date.date()} ; "
            "aucun téléchargement nécessaire."
        )
        if report_path.exists():
            return pd.read_csv(report_path, parse_dates=["latest_download_date"])
        mapping = load_yahoo_mapping(
            prices.columns,
            universe_path=universe_path,
            override_path=mapping_path,
        )
        mapping["refresh_status"] = "UP_TO_DATE"
        return mapping

    mapping = load_yahoo_mapping(
        prices.columns,
        universe_path=universe_path,
        override_path=mapping_path,
    )
    download_start = last_source_date - pd.Timedelta(days=cfg.overlap_days)
    downloaded_prices, downloaded_volumes = download_yahoo_history(
        mapping,
        start=download_start,
        end=end,
        batch_size=cfg.batch_size,
    )
    report = validate_download(
        prices,
        downloaded_prices,
        mapping,
        last_source_date=last_source_date,
        config=cfg,
    )

    new_volumes = downloaded_volumes.loc[downloaded_volumes.index > last_source_date]
    volume_counts = new_volumes.notna().sum()
    report["new_volume_observations"] = report["id"].map(volume_counts).fillna(0).astype(int)
    report.loc[
        report["refresh_status"].eq("VALIDATED") & report["new_volume_observations"].eq(0),
        "refresh_status",
    ] = "NO_NEW_VOLUME"

    updated_prices = merge_validated_history(
        prices,
        downloaded_prices,
        report,
        last_source_date=last_source_date,
    )
    updated_volumes = merge_validated_history(
        volumes,
        downloaded_volumes,
        report,
        last_source_date=last_source_date,
    )

    prices_path.parent.mkdir(parents=True, exist_ok=True)
    updated_prices.to_csv(prices_path, compression="gzip")
    updated_volumes.to_csv(volumes_path, compression="gzip")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report.sort_values(["refresh_status", "id"]).to_csv(report_path, index=False)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Actualise les prix et volumes nécessaires aux features Elastic Net depuis Yahoo. "
            "Le benchmark WLS n'est jamais remplacé par un proxy."
        )
    )
    parser.add_argument(
        "--end",
        type=pd.Timestamp,
        default=pd.Timestamp.today().normalize(),
        help="Dernière date à demander, au format YYYY-MM-DD (aujourd'hui par défaut).",
    )
    parser.add_argument("--batch-size", type=int, default=RefreshConfig.batch_size)
    parser.add_argument(
        "--maximum-median-relative-error",
        type=float,
        default=RefreshConfig.maximum_median_relative_error,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = RefreshConfig(
        batch_size=args.batch_size,
        maximum_median_relative_error=args.maximum_median_relative_error,
    )
    report = refresh_market_data(end=args.end, config=config)
    counts = report["refresh_status"].value_counts().sort_index()
    print("\nRésultat du rafraîchissement :")
    print(counts.to_string())
    validated = report[report["refresh_status"].eq("VALIDATED")]
    if validated.empty and not report["refresh_status"].eq("UP_TO_DATE").all():
        raise RuntimeError("Aucun titre n'a passé les contrôles de cohérence.")
    print(f"\nRapport : {REPORT_PATH}")
    print(
        "Benchmark WLS non modifié : fournir un export Bloomberg séparé pour actualiser "
        "la cible et le suivi relatif."
    )


if __name__ == "__main__":
    main()
