"""Offline MVP entry point: python -m macro_engine.run --date 2026-10-16."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from macro_engine import config as cfg
from macro_engine.analogues import (
    AnalogueResult,
    ablation_fragility,
    find_analogues,
    sensitivity,
    stability_counts,
)
from macro_engine.normalize import normalize
from macro_engine.reference import ReferenceData, load_reference
from macro_engine.regimes import label_regimes
from macro_engine.state import DailyState, build_state


@dataclass(frozen=True)
class VariantRun:
    ablation: str
    state: DailyState
    labels: pd.DataFrame
    analogues: AnalogueResult
    sensitivities: dict[tuple[int, float], AnalogueResult]
    robust: AnalogueResult
    review_analogues: pd.DataFrame


def compute_variant(reference, date, sample, mode, *, include_news=True) -> VariantRun:
    state = build_state(reference, date, sample, mode, include_news=include_news)
    normalized = normalize(state)
    analogues = find_analogues(normalized)
    variants = sensitivity(normalized)
    counts = stability_counts(analogues, variants)
    review = analogues.episodes.merge(
        counts, on="representative_date", how="left", validate="one_to_one"
    )
    review = review.rename(
        columns={
            "exact": "stability_exact",
            "within_episode": "stability_episode",
            "variants": "stability_variants",
        }
    )
    ablation = "with_news" if include_news else "without_news"
    review.insert(3, "ablation", ablation)
    return VariantRun(
        ablation,
        state,
        label_regimes(state),
        analogues,
        variants,
        find_analogues(normalize(state, method="robust")),
        review,
    )


def compute_run(reference: ReferenceData, date, sample="H", mode="strict") -> list[VariantRun]:
    query = pd.Timestamp(date).normalize()
    if query > max(frame.date.max() for frame in reference.observations.values()):
        raise ValueError(
            "Query beyond reference coverage: an explicitly approved new cache is required."
        )
    # The same independently cut input boundary is also used by historical runs.
    cut = reference.truncated(query)
    primary = compute_variant(cut, query, sample, mode)
    if mode != "strict":
        return [primary]
    ablated = compute_variant(cut, query, sample, mode, include_news=False)
    primary.review_analogues["fragile_without_news"] = ablation_fragility(
        primary.analogues, ablated.analogues
    ).to_numpy()
    return [primary, ablated]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Macro MVP: pinned offline reference, no portfolio decisions."
    )
    parser.add_argument("--date", default=cfg.QUERY_DATE)
    parser.add_argument("--sample", choices=cfg.SAMPLE_VARIABLES, default="H")
    parser.add_argument("--mode", choices=("strict", "descriptive"), default="strict")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv=None) -> None:
    from macro_engine.export import export_run

    args = parse_args(argv)
    reference = load_reference()
    runs = compute_run(reference, args.date, args.sample, args.mode)
    destination = args.output_dir or cfg.OUTPUT_ROOT / f"{args.date}_{args.sample}_{args.mode}"
    manifest = export_run(reference, runs, destination)
    print(f"Outputs: {destination.resolve()}")
    for run in runs:
        print(
            f"{run.ablation}: {len(run.review_analogues)} analogues; "
            f"labels through {run.state.query_date.date()}"
        )
    print(f"Input reference: {manifest['reference_cache']}")


if __name__ == "__main__":
    main()
