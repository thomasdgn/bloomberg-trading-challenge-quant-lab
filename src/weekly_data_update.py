from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_TEMPLATE = Path("data/templates/weekly_data_template.xlsx")
DEFAULT_DATA_ROOT = Path("data/bloomberg/data")
EPS_HISTORY_PATH = Path("data/eps_history_5y.csv.gz")

MARKET_SHEET = "Donnees marche"
BENCHMARK_SHEET = "Benchmark"
SNAPSHOT_SHEET = "Snapshot features"
FX_SHEET = "FX"
OPPORTUNITY_SHEET = "Univers opportuniste"

MARKET_COLUMNS = ["date", "id", "px_last", "volume"]
BENCHMARK_COLUMNS = ["date", "px_last"]
FX_COLUMNS = ["date", "currency", "usd_rate"]
OPPORTUNITY_COLUMNS = ["id", "yahoo_ticker", "enabled", "source", "notes"]
SNAPSHOT_COLUMNS = [
    "id",
    "as_of_date",
    "ticker_exchange",
    "name",
    "index_weight_pct",
    "index_position_source",
    "px_last_universe",
    "index_weight",
    "px_last",
    "volume_latest",
    "market_cap",
    "sector",
    "mom_1m",
    "mom_3m",
    "mom_6m",
    "eps_actual_latest_quarter",
    "eps_estimate_now",
    "eps_estimate_now_date",
    "eps_estimate_1m_ago",
    "eps_estimate_1m_ago_date",
    "eps_estimate_3m_ago",
    "eps_estimate_3m_ago_date",
    "roe_now_pct",
    "roe_now_pct_date",
    "roe_3m_ago_pct",
    "roe_3m_ago_pct_date",
    "debt_now",
    "debt_now_date",
    "assets_now",
    "assets_now_date",
    "debt_3m_ago",
    "debt_3m_ago_date",
    "assets_3m_ago",
    "assets_3m_ago_date",
    "leverage_now",
    "leverage_3m_ago",
    "eps_num_up_1m",
    "eps_num_down_1m",
    "revision_breadth_1m",
    "eps_num_up_3m",
    "eps_num_down_3m",
    "revision_breadth_3m",
    "currency",
    "yahoo_ticker",
]

SNAPSHOT_OUTPUTS = {
    "universe.csv": [
        "id",
        "ticker_exchange",
        "name",
        "index_weight_pct",
        "index_position_source",
        "px_last_universe",
        "index_weight",
    ],
    "static.csv": [
        "id",
        "as_of_date",
        "px_last",
        "volume_latest",
        "market_cap",
        "sector",
        "currency",
        "yahoo_ticker",
    ],
    "momentum.csv": ["id", "as_of_date", "px_last", "mom_1m", "mom_3m", "mom_6m"],
    "eps_actual.csv": ["id", "as_of_date", "eps_actual_latest_quarter"],
    "eps_estimates.csv": [
        "id",
        "as_of_date",
        "eps_estimate_now",
        "eps_estimate_now_date",
        "eps_estimate_1m_ago",
        "eps_estimate_1m_ago_date",
        "eps_estimate_3m_ago",
        "eps_estimate_3m_ago_date",
    ],
    "roe.csv": [
        "id",
        "as_of_date",
        "roe_now_pct",
        "roe_now_pct_date",
        "roe_3m_ago_pct",
        "roe_3m_ago_pct_date",
    ],
    "leverage.csv": [
        "id",
        "as_of_date",
        "debt_now",
        "debt_now_date",
        "assets_now",
        "assets_now_date",
        "debt_3m_ago",
        "debt_3m_ago_date",
        "assets_3m_ago",
        "assets_3m_ago_date",
        "leverage_now",
        "leverage_3m_ago",
    ],
    "revision_breadth.csv": [
        "id",
        "as_of_date",
        "eps_num_up_1m",
        "eps_num_down_1m",
        "revision_breadth_1m",
        "eps_num_up_3m",
        "eps_num_down_3m",
        "revision_breadth_3m",
    ],
    "rmom_inputs.csv": ["id", "as_of_date", "mom_1m", "mom_3m"],
}


def _clean_sheet(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.dropna(how="all").copy()
    result.columns = [str(column).strip() for column in result.columns]
    return result


def load_weekly_template(path: Path) -> dict[str, pd.DataFrame]:
    workbook = pd.ExcelFile(path)
    required_sheets = {
        MARKET_SHEET,
        BENCHMARK_SHEET,
        SNAPSHOT_SHEET,
        FX_SHEET,
        OPPORTUNITY_SHEET,
    }
    missing = required_sheets - set(workbook.sheet_names)
    if missing:
        raise ValueError(f"Onglets absents : {sorted(missing)}")
    return {
        name: _clean_sheet(pd.read_excel(workbook, sheet_name=name)) for name in required_sheets
    }


def validate_weekly_data(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    checks: list[dict[str, str]] = []

    def add(check: str, status: str, detail: str) -> None:
        checks.append({"check": check, "status": status, "detail": detail})

    requirements = {
        MARKET_SHEET: MARKET_COLUMNS,
        BENCHMARK_SHEET: BENCHMARK_COLUMNS,
        SNAPSHOT_SHEET: SNAPSHOT_COLUMNS,
        FX_SHEET: FX_COLUMNS,
        OPPORTUNITY_SHEET: OPPORTUNITY_COLUMNS,
    }
    for sheet, columns in requirements.items():
        missing = sorted(set(columns) - set(sheets[sheet].columns))
        add(
            f"Colonnes {sheet}",
            "ERROR" if missing else "PASS",
            f"Colonnes manquantes : {missing}" if missing else "Colonnes présentes",
        )

    if any(row["status"] == "ERROR" for row in checks):
        return pd.DataFrame(checks)

    market = sheets[MARKET_SHEET]
    benchmark = sheets[BENCHMARK_SHEET]
    snapshot = sheets[SNAPSHOT_SHEET]
    fx = sheets[FX_SHEET]
    opportunity = sheets[OPPORTUNITY_SHEET]

    for frame, column in ((market, "date"), (benchmark, "date"), (snapshot, "as_of_date")):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    if not fx.empty:
        fx["date"] = pd.to_datetime(fx["date"], errors="coerce")
    for column in ("px_last", "volume"):
        market[column] = pd.to_numeric(market[column], errors="coerce")
    benchmark["px_last"] = pd.to_numeric(benchmark["px_last"], errors="coerce")
    if not fx.empty:
        fx["usd_rate"] = pd.to_numeric(fx["usd_rate"], errors="coerce")

    for label, frame, keys in (
        (MARKET_SHEET, market, ["date", "id"]),
        (BENCHMARK_SHEET, benchmark, ["date"]),
        (SNAPSHOT_SHEET, snapshot, ["id"]),
        (FX_SHEET, fx, ["date", "currency"]),
        (OPPORTUNITY_SHEET, opportunity, ["id"]),
    ):
        duplicate_count = int(frame.duplicated(keys).sum()) if not frame.empty else 0
        add(
            f"Clés uniques {label}",
            "ERROR" if duplicate_count else "PASS",
            f"{duplicate_count} doublon(s)",
        )

    invalid_market = int(
        market["date"].isna().sum()
        + market["id"].isna().sum()
        + market["px_last"].isna().sum()
        + market["px_last"].le(0).sum()
        + market["volume"].isna().sum()
        + market["volume"].lt(0).sum()
    )
    add(
        "Valeurs marché",
        "ERROR" if invalid_market else "PASS",
        f"{invalid_market} date, identifiant, prix ou volume invalide(s)",
    )
    invalid_benchmark = int(
        benchmark["date"].isna().sum()
        + benchmark["px_last"].isna().sum()
        + benchmark["px_last"].le(0).sum()
    )
    add(
        "Valeurs benchmark",
        "ERROR" if invalid_benchmark else "PASS",
        f"{invalid_benchmark} date ou niveau WLS invalide(s)",
    )
    invalid_snapshot = int(snapshot["id"].isna().sum() + snapshot["as_of_date"].isna().sum())
    add(
        "Valeurs snapshot",
        "ERROR" if invalid_snapshot else "PASS",
        f"{invalid_snapshot} identifiant ou date invalide(s)",
    )
    provided_fx = fx[fx["usd_rate"].notna()].copy()
    invalid_fx = 0
    if not provided_fx.empty:
        invalid_fx = int(
            provided_fx["date"].isna().sum()
            + provided_fx["currency"].isna().sum()
            + provided_fx["usd_rate"].le(0).sum()
        )
    add(
        "Taux de change",
        "WARNING" if provided_fx.empty else ("ERROR" if invalid_fx else "PASS"),
        "Aucun taux FX : les quantités d'actions resteront indisponibles"
        if provided_fx.empty
        else f"{len(provided_fx)} taux fourni(s), {invalid_fx} valeur(s) invalide(s)",
    )

    enabled = opportunity["enabled"].astype(str).str.strip().str.lower()
    active_mapping = opportunity[enabled.isin({"true", "1", "yes", "oui"})]
    invalid_mapping = int(
        active_mapping["id"].isna().sum()
        + active_mapping["yahoo_ticker"].isna().sum()
        + active_mapping["yahoo_ticker"].astype(str).str.strip().eq("").sum()
        + active_mapping["yahoo_ticker"].duplicated().sum()
    )
    add(
        "Symboles Yahoo actifs",
        "WARNING" if active_mapping.empty else ("ERROR" if invalid_mapping else "PASS"),
        (
            "Aucun symbole actif pour le modèle opportuniste"
            if active_mapping.empty
            else f"{len(active_mapping)} symbole(s) actif(s), {invalid_mapping} erreur(s)"
        ),
    )

    snapshot_currencies = set(snapshot["currency"].dropna().astype(str).str.upper())
    fx_currencies = set(provided_fx["currency"].dropna().astype(str).str.upper())
    missing_fx = sorted(snapshot_currencies - fx_currencies)
    add(
        "Couverture FX du snapshot",
        "WARNING" if missing_fx or not snapshot_currencies else "PASS",
        (
            f"Devises sans taux : {missing_fx}"
            if missing_fx
            else (
                "Aucune devise renseignée dans le snapshot"
                if not snapshot_currencies
                else f"{len(snapshot_currencies)} devise(s) couverte(s)"
            )
        ),
    )

    latest_market = market["date"].max()
    latest_benchmark = benchmark["date"].max()
    latest_snapshot = snapshot["as_of_date"].max()
    dates_match = latest_market == latest_benchmark == latest_snapshot
    add(
        "Dates de clôture alignées",
        "PASS" if dates_match else "ERROR",
        (
            f"marché={latest_market.date()}, benchmark={latest_benchmark.date()}, "
            f"snapshot={latest_snapshot.date()}"
        ),
    )
    return pd.DataFrame(checks)


def _update_wide_history(path: Path, updates: pd.DataFrame, value_column: str) -> None:
    existing = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    wide_update = updates.pivot(index="date", columns="id", values=value_column)
    all_dates = existing.index.union(wide_update.index).sort_values()
    all_assets = existing.columns.union(wide_update.columns, sort=False)
    combined = existing.reindex(index=all_dates, columns=all_assets)
    aligned_update = wide_update.reindex(index=all_dates, columns=all_assets)
    combined = combined.where(aligned_update.isna(), aligned_update)
    combined.index.name = "date"
    combined.reset_index().to_csv(path, index=False, compression="gzip")


def _update_benchmark(path: Path, updates: pd.DataFrame) -> None:
    existing = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    incoming = updates.set_index("date")[["px_last"]]
    all_dates = existing.index.union(incoming.index).sort_values()
    combined = existing.reindex(all_dates)
    aligned = incoming.reindex(all_dates)
    combined = combined.where(aligned.isna(), aligned)
    combined.index.name = "date"
    combined.reset_index().to_csv(path, index=False)


def _update_eps_history(snapshot: pd.DataFrame, path: Path) -> None:
    eps = pd.read_csv(path, index_col="month")
    latest_date = pd.Timestamp(snapshot["as_of_date"].max())
    month = latest_date.to_period("M").strftime("%Y-%m")
    current = snapshot.set_index("id")["eps_estimate_now"]
    all_assets = eps.columns.union(current.index, sort=False)
    eps = eps.reindex(columns=all_assets)
    eps.loc[month, current.index] = current.to_numpy()
    eps.sort_index().to_csv(path, compression="gzip")


def apply_weekly_data(
    sheets: dict[str, pd.DataFrame],
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    eps_history_path: Path = EPS_HISTORY_PATH,
) -> None:
    market = sheets[MARKET_SHEET].copy()
    benchmark = sheets[BENCHMARK_SHEET].copy()
    snapshot = sheets[SNAPSHOT_SHEET].copy()
    fx = sheets[FX_SHEET].copy()
    opportunity = sheets[OPPORTUNITY_SHEET].copy()
    market["date"] = pd.to_datetime(market["date"])
    benchmark["date"] = pd.to_datetime(benchmark["date"])
    snapshot["as_of_date"] = pd.to_datetime(snapshot["as_of_date"])

    _update_wide_history(data_root / "prices_10y.csv.gz", market, "px_last")
    _update_wide_history(data_root / "volumes_10y.csv.gz", market, "volume")
    _update_benchmark(data_root / "benchmark_10y.csv", benchmark)

    snapshot.to_csv(data_root / "features_snapshot.csv", index=False)
    for filename, columns in SNAPSHOT_OUTPUTS.items():
        snapshot[columns].to_csv(data_root / filename, index=False)
    _update_eps_history(snapshot, eps_history_path)

    if not fx.empty:
        fx["date"] = pd.to_datetime(fx["date"])
        fx["usd_rate"] = pd.to_numeric(fx["usd_rate"], errors="coerce")
        fx[fx["usd_rate"].notna()].to_csv(data_root / "fx_rates.csv", index=False)

    enabled = opportunity["enabled"].astype(str).str.strip().str.lower()
    opportunity = opportunity[enabled.isin({"true", "1", "yes", "oui"})]
    opportunity[OPPORTUNITY_COLUMNS].to_csv(data_root / "yahoo_mapping.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valide puis importe le template de données hebdomadaires."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Met à jour les fichiers Bloomberg. Sans ce flag, aucune donnée n'est modifiée.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sheets = load_weekly_template(args.input)
    checks = validate_weekly_data(sheets)
    print(checks.to_string(index=False))
    if checks["status"].eq("ERROR").any():
        raise RuntimeError("Le template contient des erreurs. Aucun fichier n'a été modifié.")
    if args.apply:
        apply_weekly_data(sheets)
        print("Données hebdomadaires importées.")
    else:
        print("Validation terminée. Relancer avec --apply pour importer les données.")


if __name__ == "__main__":
    main()
