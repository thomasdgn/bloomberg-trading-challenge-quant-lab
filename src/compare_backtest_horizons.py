from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_WEEKLY_PATH = Path("data/processed/execution_backtest/v1_1w_sans_stop/periods.csv")
DEFAULT_FIVE_WEEK_PATH = Path("data/processed/execution_backtest/v1_sans_stop/periods.csv")
DEFAULT_OUTPUT_DIR = Path("data/processed/execution_backtest/horizon_comparison")


def max_drawdown(returns: pd.Series) -> float:
    wealth = (1.0 + returns).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def summarize_path(group: pd.DataFrame, horizon_weeks: int) -> dict[str, float | int | str]:
    suffix = f"{horizon_weeks}w"
    net = group[f"net_return_{suffix}"].astype(float)
    benchmark = group[f"benchmark_return_{suffix}"].astype(float)
    excess = group[f"net_excess_{suffix}"].astype(float)
    years = len(group) * horizon_weeks / 52.0
    net_wealth = float((1.0 + net).prod())
    benchmark_wealth = float((1.0 + benchmark).prod())
    annualized_net = net_wealth ** (1.0 / years) - 1.0
    annualized_benchmark = benchmark_wealth ** (1.0 / years) - 1.0
    annualized_relative = (net_wealth / benchmark_wealth) ** (1.0 / years) - 1.0
    annualized_excess_volatility = float(excess.std() * np.sqrt(52.0 / horizon_weeks))
    information_ratio = (
        np.nan
        if excess.std() == 0 or np.isnan(excess.std())
        else float(excess.mean() / excess.std() * np.sqrt(52.0 / horizon_weeks))
    )
    return {
        "n_periods": len(group),
        "start_date": str(group["date"].min().date()),
        "end_date": str(group["end_date"].max().date()),
        "mean_net_excess_per_period": float(excess.mean()),
        "median_net_excess_per_period": float(excess.median()),
        "win_rate": float(excess.gt(0).mean()),
        "mean_one_way_turnover": float(group["one_way_turnover"].mean()),
        "annualized_one_way_turnover": float(
            group["one_way_turnover"].mean() * 52.0 / horizon_weeks
        ),
        "mean_cost_per_period": float(group["total_cost_return"].mean()),
        "annualized_cost_linear": float(group["total_cost_return"].mean() * 52.0 / horizon_weeks),
        "annualized_net_return": annualized_net,
        "annualized_benchmark_return": annualized_benchmark,
        "annualized_relative_return": annualized_relative,
        "equivalent_relative_return_5w": (1.0 + annualized_relative) ** (5.0 / 52.0) - 1.0,
        "annualized_excess_volatility": annualized_excess_volatility,
        "information_ratio": information_ratio,
        "max_drawdown": max_drawdown(net),
    }


def compare_horizons(
    weekly: pd.DataFrame,
    five_week: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = {
        "1 semaine, rebalancement hebdomadaire": (weekly.copy(), 1),
        "5 semaines, conservation": (five_week.copy(), 5),
    }
    for frame, _ in frames.values():
        frame["date"] = pd.to_datetime(frame["date"])
        frame["end_date"] = pd.to_datetime(frame["end_date"])

    common_start = max(frame["date"].min() for frame, _ in frames.values())
    common_end = min(frame["end_date"].max() for frame, _ in frames.values())
    path_rows = []
    for strategy, (frame, horizon_weeks) in frames.items():
        comparable = frame[frame["date"].ge(common_start) & frame["end_date"].le(common_end)].copy()
        for offset, group in comparable.groupby("offset"):
            ordered = group.sort_values("date")
            path_rows.append(
                {
                    "strategy": strategy,
                    "horizon_weeks": horizon_weeks,
                    "offset": int(offset),
                    **summarize_path(ordered, horizon_weeks),
                }
            )

    by_path = pd.DataFrame(path_rows)
    metric_columns = [
        column
        for column in by_path.columns
        if column not in {"strategy", "horizon_weeks", "offset", "start_date", "end_date"}
    ]
    summary = (
        by_path.groupby(["strategy", "horizon_weeks"], as_index=False)[metric_columns]
        .mean()
        .sort_values("horizon_weeks")
        .reset_index(drop=True)
    )
    worst_drawdown = by_path.groupby("strategy")["max_drawdown"].min()
    summary["worst_max_drawdown_by_path"] = summary["strategy"].map(worst_drawdown)
    summary.insert(2, "common_start", str(common_start.date()))
    summary.insert(3, "common_end", str(common_end.date()))
    summary.insert(
        4,
        "n_paths",
        summary["strategy"].map(by_path.groupby("strategy")["offset"].nunique()),
    )
    return summary, by_path


def render_markdown(summary: pd.DataFrame) -> str:
    displayed = summary.copy()
    percent_columns = [
        column
        for column in displayed.columns
        if any(
            token in column
            for token in ("return", "excess", "win_rate", "turnover", "cost", "drawdown")
        )
    ]
    for column in percent_columns:
        displayed[column] = displayed[column].map(lambda value: f"{value:.2%}")
    displayed["information_ratio"] = displayed["information_ratio"].map(
        lambda value: "" if pd.isna(value) else f"{value:.2f}"
    )
    header = "| " + " | ".join(displayed.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(displayed.columns)) + " |"
    rows = [
        "| " + " | ".join(map(str, row)) + " |"
        for row in displayed.itertuples(index=False, name=None)
    ]
    return "\n".join(
        [
            "# Comparaison des horizons de backtest",
            "",
            "La comparaison utilise la même fenêtre historique commune. Le backtest "
            "1 semaine forme une seule trajectoire séquentielle. Le backtest 5 semaines "
            "est résumé sur ses cinq trajectoires non chevauchantes.",
            "",
            header,
            separator,
            *rows,
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare les backtests 1 et 5 semaines.")
    parser.add_argument("--weekly", type=Path, default=DEFAULT_WEEKLY_PATH)
    parser.add_argument("--five-week", type=Path, default=DEFAULT_FIVE_WEEK_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    weekly = pd.read_csv(args.weekly, parse_dates=["date", "end_date"])
    five_week = pd.read_csv(args.five_week, parse_dates=["date", "end_date"])
    summary, by_path = compare_horizons(weekly, five_week)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output_dir / "comparison_summary.csv", index=False)
    by_path.to_csv(args.output_dir / "comparison_by_path.csv", index=False)
    (args.output_dir / "comparison.md").write_text(render_markdown(summary), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Comparaison créée dans {args.output_dir}")


if __name__ == "__main__":
    main()
