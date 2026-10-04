"""Synthetic workbooks exercise the import without sharing Bloomberg exports."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from import_wls import ImportValidationError, load_snapshot, write_snapshot

HEADERS = [
    "ID",
    "px_last().value",
    "avg(turnover(currency=USd,end=2026-10-02,start=2026-09-02))",
    *[
        f"total_return(calc_interval=range({start},2026-10-02),"
        "display_returns=PERCENT,side=BID).value"
        for start in ["2026-09-02", "2026-07-02", "2026-04-02"]
    ],
    "volatility(calc_interval=range(2026-07-02,2026-10-02),tr_base=PRICE_IF_AVAILABLE).value",
]


def workbook(tmp_path, rows=None, headers=None):
    path = tmp_path / "synthetic.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "WLSIndexData"
    sheet.append(HEADERS if headers is None else headers)
    for row in (
        rows if rows is not None else [["000001 HK Equity", 10, 600_000_000, 0.15, 0.2, -0.1, 0.3]]
    ):
        sheet.append(row)
    book.save(path)
    book.close()
    return path


def test_round_trip_preserves_raw_values_identity_and_source(tmp_path):
    source = workbook(tmp_path)
    before = source.read_bytes()
    snapshot = load_snapshot(source)
    write_snapshot(snapshot, tmp_path / "result", source)
    output = pd.read_parquet(tmp_path / "result/snapshot.parquet")
    assert output.loc[0, "security_id"] == "000001 HK Equity"
    assert output.loc[0, "total_return_1m_raw"] == 0.15
    assert output.loc[0, "total_return_6m_raw"] == -0.1
    assert output.loc[0, "source_excel_row"] == 2
    assert source.read_bytes() == before
    assert output.loc[0, "source_sha256"] == hashlib.sha256(before).hexdigest()
    report = json.loads((tmp_path / "result/report.json").read_text(encoding="utf-8"))
    assert report["row_count"] == report["complete_numeric_rows"] == 1
    assert report["indicator_end_date"] == "2026-10-02"
    assert report["price_effective_date"] is None
    assert report["ready_for_backtest"] is False
    assert report["financial_conventions_verified"] is False
    assert pd.read_csv(tmp_path / "result/anomalies.csv").empty
    dictionary = json.loads((tmp_path / "result/data_dictionary.json").read_text(encoding="utf-8"))
    assert dictionary["columns"][3]["unit"] == "à confirmer"
    assert dictionary["columns"][3]["period_start"] == "2026-09-02"


@pytest.mark.parametrize("missing, code", [("#N/A", "excel_error"), (None, "missing_value")])
def test_missing_volatility_keeps_the_title_and_explains_the_null(tmp_path, missing, code):
    source = workbook(tmp_path, [["FAKE UN Equity", 10, 500_000_000, 0.1, 0.2, 0.3, missing]])
    snapshot = load_snapshot(source)
    assert len(snapshot.table) == 1
    assert pd.isna(snapshot.table.loc[0, "volatility_3m_raw"])
    assert snapshot.report["complete_numeric_rows"] == 0
    assert snapshot.report["missing_by_column"]["volatility_3m_raw"] == 1
    assert snapshot.anomalies.loc[0, "code"] == code
    assert snapshot.anomalies.loc[0, "cell"] == "G2"
    write_snapshot(snapshot, tmp_path / "missing", source)
    assert pd.isna(
        pd.read_parquet(tmp_path / "missing/snapshot.parquet").loc[0, "volatility_3m_raw"]
    )


def test_identical_horizons_are_flagged_without_changing_returns(tmp_path):
    snapshot = load_snapshot(
        workbook(tmp_path, [["FAKE UN Equity", 10, 500_000_000, 0.1, 0.1, 0.1, 0.3]])
    )
    assert snapshot.anomalies.loc[0, "code"] == "identical_horizon_returns"
    assert snapshot.table.loc[0, "total_return_3m_raw"] == 0.1


def test_duplicates_are_rejected_instead_of_silently_dropped(tmp_path):
    row = ["FAKE UN Equity", 10, 500_000_000, 0.1, 0.2, 0.3, 0.4]
    with pytest.raises(ImportValidationError, match="dupliqué"):
        load_snapshot(workbook(tmp_path, [row, row]))


@pytest.mark.parametrize("value", ["10,5", True, "=1+2", -1, 0])
def test_ambiguous_or_invalid_prices_stop_the_import(tmp_path, value):
    with pytest.raises(ImportValidationError):
        load_snapshot(
            workbook(tmp_path, [["FAKE UN Equity", value, 500_000_000, 0.1, 0.2, 0.3, 0.4]])
        )


def test_different_end_dates_are_rejected(tmp_path):
    headers = HEADERS.copy()
    headers[4] = headers[4].replace("2026-10-02", "2026-10-03")
    with pytest.raises(ImportValidationError, match="divergent"):
        load_snapshot(workbook(tmp_path, headers=headers))


def test_wrong_horizon_is_rejected_even_when_end_dates_match(tmp_path):
    headers = HEADERS.copy()
    headers[4] = headers[4].replace("2026-07-02", "2026-08-02")
    with pytest.raises(ImportValidationError, match="divergent"):
        load_snapshot(workbook(tmp_path, headers=headers))


@pytest.mark.parametrize("headers", [HEADERS[:-1], [*HEADERS, "UNEXPECTED"]])
def test_schema_changes_are_not_silently_accepted(tmp_path, headers):
    with pytest.raises(ImportValidationError):
        load_snapshot(workbook(tmp_path, rows=[], headers=headers))


def test_populated_extra_columns_are_rejected(tmp_path):
    row = ["FAKE UN Equity", 10, 500_000_000, 0.1, 0.2, 0.3, 0.4, "extra"]
    with pytest.raises(ImportValidationError, match="hors des sept"):
        load_snapshot(workbook(tmp_path, [row]))


def test_empty_sheet_and_missing_sheet_are_rejected(tmp_path):
    source = workbook(tmp_path, rows=[])
    with pytest.raises(ImportValidationError, match="aucun titre"):
        load_snapshot(source)
    with pytest.raises(ImportValidationError, match="Feuille absente"):
        load_snapshot(source, "Missing")


def test_previous_import_and_source_directory_are_not_overwritten(tmp_path):
    source = workbook(tmp_path)
    snapshot = load_snapshot(source)
    out = tmp_path / "result"
    write_snapshot(snapshot, out, source)
    before = (out / "snapshot.parquet").read_bytes()
    with pytest.raises(ImportValidationError, match="existe déjà"):
        write_snapshot(snapshot, out, source)
    assert (out / "snapshot.parquet").read_bytes() == before
    with pytest.raises(ImportValidationError, match="fichier source"):
        write_snapshot(snapshot, tmp_path, source)


def test_failed_export_does_not_publish_partial_results(tmp_path, monkeypatch):
    source = workbook(tmp_path)
    snapshot = load_snapshot(source)

    def fail(*args, **kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(snapshot.table, "to_parquet", fail)
    with pytest.raises(OSError, match="disk failure"):
        write_snapshot(snapshot, tmp_path / "failed", source)
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".wls-import-*"))


def test_cli_success_and_missing_file_error(tmp_path):
    source = workbook(tmp_path)
    script = Path(__file__).resolve().parents[1] / "src/import_wls.py"
    args = [
        sys.executable,
        str(script),
        "--input",
        str(source),
        "--output-dir",
        str(tmp_path / "cli"),
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "cli/report.json").exists()
    args[3] = str(tmp_path / "absent.xlsx")
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Import arrêté" in result.stderr
    assert "Traceback" not in result.stderr
