"""Actual serialized outputs: identity, lineage, no mixing, safe destinations."""

import json

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from macro_engine import config as cfg
from macro_engine.export import export_run, sha256
from macro_engine.run import compute_run, main


@pytest.fixture(scope="module")
def runs(reference):
    return compute_run(reference, cfg.QUERY_DATE)


def test_all_eight_exports_and_bitwise_determinism(reference, runs, tmp_path):
    first = export_run(reference, runs, tmp_path / "first")
    again = export_run(reference, compute_run(reference, cfg.QUERY_DATE), tmp_path / "again")
    expected = {
        "macro_raw.parquet",
        "macro_pit.parquet",
        "macro_state_daily.parquet",
        "macro_regimes.csv",
        "historical_analogues.csv",
        "source_registry.csv",
        "macro_diagnostics.html",
        "run_manifest.json",
    }
    assert {p.name for p in (tmp_path / "first").iterdir()} == expected
    for filename in expected:
        assert (tmp_path / "first" / filename).read_bytes() == (
            tmp_path / "again" / filename
        ).read_bytes()
    assert first == again
    for filename, digest in first["output_sha256"].items():
        assert sha256((tmp_path / "first" / filename).read_bytes()) == digest
    assert first["reference_cache"] == cfg.REFERENCE_CACHE
    assert first["spec_sha256"] == cfg.SPEC_SHA256
    assert "FRED_API_KEY" not in json.dumps(first)
    assert "DTWEXM" not in json.dumps(first)
    html = (tmp_path / "first" / "macro_diagnostics.html").read_text(encoding="utf-8")
    assert "<script src=" not in html
    assert "Plotly.newPlot" in html
    assert "with_news_map" in html and "without_news_map" in html
    assert "DTWEXM" not in html


def test_exported_data_lineage_availability_and_join_keys(reference, runs, tmp_path):
    export_run(reference, runs, tmp_path)
    daily = pd.read_parquet(tmp_path / "macro_state_daily.parquet")
    assert not daily.duplicated(["date", "sample", "mode", "ablation"]).any()
    assert daily["sample"].eq("H").all() and daily["mode"].eq("strict").all()
    assert "DTWEXBGS" not in daily
    pit = pd.read_parquet(tmp_path / "macro_pit.parquet")
    assert pit.available_at.le(pd.Timestamp(cfg.QUERY_DATE)).all()
    assert pit.date.le(pit.available_at).all()
    assert pit[pit.identifier.eq("SP500")].date.max() == pd.Timestamp("2026-10-15")
    assert not pit["identifier"].eq("DTWEXM").any()
    raw = pd.read_parquet(tmp_path / "macro_raw.parquet")
    assert raw.record_role.eq("reference_archive_not_a_pit_signal").all()
    labels = pd.read_csv(tmp_path / "macro_regimes.csv", parse_dates=["date"])
    assert pd.isna(
        labels.loc[
            (labels.date.eq("2026-02-20")) & labels.ablation.eq("with_news"), "RALENTISSEMENT"
        ]
    ).all()
    selected = pd.read_csv(
        tmp_path / "historical_analogues.csv", parse_dates=["representative_date"]
    )
    for run in runs:
        part = selected[selected.ablation.eq(run.ablation)]
        assert (
            part.representative_date.tolist() == run.analogues.episodes.representative_date.tolist()
        )
        assert part.stability_variants.eq(9).all()


def test_exports_refuse_overwrite_cache_and_mixed_spaces(reference, runs, tmp_path):
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "kept").write_text("original")
    with pytest.raises(FileExistsError):
        export_run(reference, runs, occupied)
    assert (occupied / "kept").read_text() == "original"
    with pytest.raises(ValueError, match="cache"):
        export_run(reference, runs, cfg.CACHE_ROOT / cfg.REFERENCE_CACHE)
    with pytest.raises(ValueError, match="Never combine"):
        export_run(
            reference,
            runs + compute_run(reference, cfg.QUERY_DATE, "R", "descriptive"),
            tmp_path / "mix",
        )


def test_cli_real_end_to_end_and_short_history_absence(tmp_path):
    main(
        ["--date", "1990-08-15", "--sample", "H", "--mode", "strict", "--output-dir", str(tmp_path)]
    )
    selected = pd.read_csv(tmp_path / "historical_analogues.csv")
    assert selected.empty
    labels = pd.read_csv(tmp_path / "macro_regimes.csv")
    assert not labels.empty
    assert set(labels.ablation) == {"with_news", "without_news"}


def test_descriptive_exports_and_no_history_json_null(reference, tmp_path):
    runs = compute_run(reference, "1990-08-15", "R", "descriptive")
    manifest = export_run(reference, runs, tmp_path)
    assert manifest["normalization"]["with_news"]["center"]["DTWEXBGS"] is None
    assert_frame_equal(
        pd.read_parquet(tmp_path / "macro_state_daily.parquet")
        .drop(columns=["sample", "mode", "ablation", "as_of_date"])
        .set_index("date"),
        runs[0].state.values,
        check_exact=True,
    )
