from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.market_metadata import infer_currency

ALLOCATION_PATH = Path("data/processed/opportunistic/allocation_80_20.csv")
ORDERS_PATH = Path("data/processed/execution/execution_orders.csv")
OUTPUT_DIR = Path("data/processed/opportunistic")
CORE_OUTPUT = "core_80_clean.csv"
OPPORTUNISTIC_OUTPUT = "opportunistic_20_clean.csv"

CLEAN_COLUMNS = [
    "id",
    "currency",
    "allocation_pct",
    "allocation_usd",
    "last_price_local",
    "last_price_usd",
    "score",
    "estimated_excess_return_5w_pct",
    "estimated_excess_profit_5w_usd",
]


def build_clean_allocation_exports(
    allocation: pd.DataFrame,
    orders: pd.DataFrame,
    *,
    capital: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_allocation = {
        "id",
        "sleeve",
        "weight",
        "combined_score",
        "opportunity_score",
        "predicted_excess_return",
    }
    missing_allocation = required_allocation - set(allocation.columns)
    if missing_allocation:
        raise ValueError(
            "Colonnes manquantes dans l'allocation 80/20 : " + ", ".join(sorted(missing_allocation))
        )

    required_orders = {"id", "last_price", "price_to_usd_rate"}
    missing_orders = required_orders - set(orders.columns)
    if missing_orders:
        raise ValueError(
            "Colonnes manquantes dans le plan d'ordres : " + ", ".join(sorted(missing_orders))
        )
    if capital <= 0:
        raise ValueError("Le capital doit être strictement positif.")

    selected = allocation[allocation["weight"].astype(float).gt(1e-12)].copy()
    order_data = orders.drop_duplicates("id", keep="last").set_index("id")
    selected["last_price_local"] = selected["id"].map(order_data["last_price"])
    selected["price_to_usd_rate"] = selected["id"].map(order_data["price_to_usd_rate"])
    selected["currency"] = selected["currency"].astype("string")
    selected["currency"] = selected["currency"].fillna(selected["id"].map(infer_currency))
    selected["allocation_pct"] = 100.0 * selected["weight"].astype(float)
    selected["allocation_usd"] = capital * selected["weight"].astype(float)
    selected["last_price_usd"] = selected["last_price_local"] * selected["price_to_usd_rate"]
    selected["score"] = np.where(
        selected["sleeve"].eq("core_5w"),
        100.0 * selected["combined_score"],
        selected["opportunity_score"],
    )
    selected["estimated_excess_return_5w_pct"] = 100.0 * selected["predicted_excess_return"]
    selected["estimated_excess_profit_5w_usd"] = (
        selected["allocation_usd"] * selected["predicted_excess_return"]
    )

    selected = selected.round(
        {
            "allocation_pct": 4,
            "allocation_usd": 2,
            "last_price_local": 4,
            "last_price_usd": 4,
            "score": 2,
            "estimated_excess_return_5w_pct": 4,
            "estimated_excess_profit_5w_usd": 2,
        }
    )
    for sleeve, sleeve_rows in selected.groupby("sleeve"):
        sleeve_weight = allocation.loc[allocation["sleeve"].eq(sleeve), "weight"].sum()
        expected_total = round(capital * sleeve_weight, 2)
        rounding_residual = round(
            expected_total - sleeve_rows["allocation_usd"].sum(),
            2,
        )
        if rounding_residual:
            largest_index = sleeve_rows["allocation_usd"].idxmax()
            selected.loc[largest_index, "allocation_usd"] += rounding_residual

    missing_values = selected[CLEAN_COLUMNS].isna().sum()
    missing_values = missing_values[missing_values.gt(0)]
    if not missing_values.empty:
        details = ", ".join(f"{column}={count}" for column, count in missing_values.items())
        raise ValueError(f"Valeurs manquantes dans les exports nettoyés : {details}")

    core = (
        selected[selected["sleeve"].eq("core_5w")][CLEAN_COLUMNS]
        .sort_values("allocation_pct", ascending=False)
        .reset_index(drop=True)
    )
    opportunistic = (
        selected[selected["sleeve"].eq("opportunistic")][CLEAN_COLUMNS]
        .sort_values("allocation_pct", ascending=False)
        .reset_index(drop=True)
    )
    return core, opportunistic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporte les allocations 80/20 simplifiées.")
    parser.add_argument("--allocation", type=Path, default=ALLOCATION_PATH)
    parser.add_argument("--orders", type=Path, default=ORDERS_PATH)
    parser.add_argument("--capital", type=float, default=1_000_000.0)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    allocation = pd.read_csv(args.allocation)
    orders = pd.read_csv(args.orders)
    core, opportunistic = build_clean_allocation_exports(
        allocation,
        orders,
        capital=args.capital,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    core_path = args.output_dir / CORE_OUTPUT
    opportunistic_path = args.output_dir / OPPORTUNISTIC_OUTPUT
    core.to_csv(core_path, index=False)
    opportunistic.to_csv(opportunistic_path, index=False)
    print(f"Allocation cœur 80 % : {core_path}")
    print(core.to_string(index=False))
    print(f"\nAllocation opportuniste 20 % : {opportunistic_path}")
    print(opportunistic.to_string(index=False))


if __name__ == "__main__":
    main()
