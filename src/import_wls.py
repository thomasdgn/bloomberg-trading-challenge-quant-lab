"""Import a static Bloomberg snapshot without changing its values or source workbook."""

import argparse
import calendar
import hashlib
import json
import math
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
from openpyxl import load_workbook

COLUMNS = (
    "security_id",
    "px_last_raw",
    "turnover_raw",
    "total_return_1m_raw",
    "total_return_3m_raw",
    "total_return_6m_raw",
    "volatility_3m_raw",
)
ISSUE_COLUMNS = (
    "source_excel_row",
    "security_id",
    "cell",
    "field",
    "code",
    "severity",
    "raw_value",
    "message",
)
PENDING_CONVENTIONS = [
    "Devise et date effective du dernier prix",
    "Unité, fréquence et agrégation du turnover",
    "Échelle et devise des rendements, options BID et événements sur titres",
    "Échelle, fréquence et annualisation de la volatilité",
    "Date effective de composition et filtre de l'univers",
]


class ImportValidationError(ValueError):
    """The workbook cannot safely be represented as the expected snapshot."""


@dataclass
class Snapshot:
    table: pd.DataFrame
    anomalies: pd.DataFrame
    report: dict
    dictionary: dict


def _months_before(end: date, months: int) -> date:
    year, month_zero = divmod(end.year * 12 + end.month - 1 - months, 12)
    month = month_zero + 1
    return date(year, month, min(end.day, calendar.monthrange(year, month)[1]))


def _parse_headers(headers: tuple) -> tuple[date, list[dict]]:
    if len(headers) != 7 or headers[0] != "ID" or headers[1] != "px_last().value":
        raise ImportValidationError("En-têtes inattendus : il faut ID et les six champs Bloomberg.")
    clean = [re.sub(r"\s+", "", str(value)) for value in headers]
    patterns = [
        r"avg\(turnover\(currency=USd,end=(\d{4}-\d{2}-\d{2}),start=(\d{4}-\d{2}-\d{2})\)\)",
        *(
            r"total_return\(calc_interval=range\((\d{4}-\d{2}-\d{2}),(\d{4}-\d{2}-\d{2})\),"
            r"display_returns=PERCENT,side=BID\)\.value"
            for _ in range(3)
        ),
        r"volatility\(calc_interval=range\((\d{4}-\d{2}-\d{2}),(\d{4}-\d{2}-\d{2})\),"
        r"tr_base=PRICE_IF_AVAILABLE\)\.value",
    ]
    periods = []
    for index, (header, pattern) in enumerate(zip(clean[2:], patterns, strict=True)):
        match = re.fullmatch(pattern, header, re.IGNORECASE)
        if match is None:
            raise ImportValidationError(f"Champ Bloomberg inattendu en colonne {index + 3}.")
        try:
            first, second = map(date.fromisoformat, match.groups())
        except ValueError as exc:
            raise ImportValidationError("Une date d'en-tête est invalide.") from exc
        start, end = (second, first) if index == 0 else (first, second)
        if start >= end:
            raise ImportValidationError("Un intervalle est inversé ou vide.")
        periods.append((start, end))
    end = periods[0][1]
    for (start, period_end), months in zip(periods, [1, 1, 3, 6, 3], strict=True):
        if period_end != end or start != _months_before(end, months):
            raise ImportValidationError("Les horizons 1/3/6 mois ou leurs dates de fin divergent.")
    descriptions = [
        "Identifiant Bloomberg complet",
        "Dernier prix enregistré",
        "Turnover avec currency=USd et agrégation avg",
        "Rendement passé un mois, side=BID",
        "Rendement passé trois mois, side=BID",
        "Rendement passé six mois, side=BID",
        "Volatilité trois mois, tr_base=PRICE_IF_AVAILABLE",
    ]
    dictionary = []
    for index, (column, header, description) in enumerate(
        zip(COLUMNS, headers, descriptions, strict=True)
    ):
        period = periods[index - 2] if index >= 2 else None
        dictionary.append(
            {
                "name": column,
                "source_header": header,
                "description": description,
                "dtype": "string" if index == 0 else "float64",
                "period_start": period[0].isoformat() if period else None,
                "period_end": period[1].isoformat() if period else None,
                "unit": "Bloomberg security identifier" if index == 0 else "à confirmer",
                "transformation": "aucune conversion d'unité ; erreurs et blancs deviennent null",
            }
        )
    return end, dictionary


def load_snapshot(source: Path, sheet: str = "WLSIndexData") -> Snapshot:
    """Read all rows; reject ambiguous structure and retain missing values with explanations."""
    source = Path(source)
    if source.suffix.lower() != ".xlsx":
        raise ImportValidationError(
            "Cet import attend un .xlsx statique, sans macros à actualiser."
        )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    formulas = load_workbook(source, read_only=True, data_only=False)
    cached = None
    try:
        cached = load_workbook(source, read_only=True, data_only=True)
        if sheet not in formulas.sheetnames:
            raise ImportValidationError(f"Feuille absente : {sheet}.")
        raw_rows = formulas[sheet].iter_rows()
        value_rows = cached[sheet].iter_rows()
        header_cells, header_values = next(raw_rows), next(value_rows)
        if any(c.data_type == "f" for c in header_cells):
            raise ImportValidationError("La table doit être statique, y compris ses en-têtes.")
        headers = tuple(c.value for c in header_values)
        # Extra formatted columns are harmless; populated columns are not silently ignored.
        if any(v is not None for v in headers[7:]):
            raise ImportValidationError("Des colonnes supplémentaires sont renseignées.")
        end, dictionary = _parse_headers(headers[:7])
        records, issues, seen = [], [], set()
        blank_rows = 0
        for excel_row, (raw_cells, values) in enumerate(
            zip(raw_rows, value_rows, strict=True), start=2
        ):
            if any(c.value is not None for c in raw_cells[7:]):
                raise ImportValidationError(
                    f"Données hors des sept colonnes à la ligne {excel_row}."
                )
            if all(c.value is None for c in raw_cells):
                blank_rows += 1
                continue
            if any(c.data_type == "f" for c in raw_cells):
                raise ImportValidationError(
                    f"Formule à la ligne {excel_row} : export statique requis."
                )
            security = values[0].value
            if (
                not isinstance(security, str)
                or security != security.strip()
                or len(security.split()) != 3
                or not security.endswith(" Equity")
            ):
                raise ImportValidationError(f"Identifiant invalide à la ligne {excel_row}.")
            if security in seen:
                raise ImportValidationError(f"Identifiant dupliqué : {security}.")
            seen.add(security)
            record = {"security_id": security, "source_excel_row": excel_row}
            for index, column in enumerate(COLUMNS[1:], start=1):
                cell = values[index]
                coordinate = f"{chr(65 + index)}{excel_row}"
                value = cell.value
                if value is None or cell.data_type == "e":
                    record[column] = float("nan")
                    issues.append(
                        {
                            "source_excel_row": excel_row,
                            "security_id": security,
                            "cell": coordinate,
                            "field": column,
                            "code": "excel_error" if cell.data_type == "e" else "missing_value",
                            "severity": "warning",
                            "raw_value": value,
                            "message": "Valeur manquante conservée ; aucun remplacement par zéro.",
                        }
                    )
                elif isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ImportValidationError(f"Valeur non numérique en {coordinate}.")
                elif not math.isfinite(value):
                    raise ImportValidationError(f"Valeur non finie en {coordinate}.")
                elif index in (1, 2, 6) and value <= 0:
                    raise ImportValidationError(
                        f"Prix, turnover ou volatilité non positif en {coordinate}."
                    )
                else:
                    record[column] = float(value)
            returns = [record[c] for c in COLUMNS[3:6]]
            if all(math.isfinite(v) for v in returns) and len(set(returns)) == 1:
                issues.append(
                    {
                        "source_excel_row": excel_row,
                        "security_id": security,
                        "cell": f"D{excel_row}:F{excel_row}",
                        "field": "return_horizons",
                        "code": "identical_horizon_returns",
                        "severity": "warning",
                        "raw_value": returns[0],
                        "message": (
                            "Rendements 1/3/6 mois identiques : "
                            "vérifier la longueur de l'historique."
                        ),
                    }
                )
            records.append(record)
    finally:
        formulas.close()
        if cached is not None:
            cached.close()
    if not records:
        raise ImportValidationError("La table ne contient aucun titre.")
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ImportValidationError("Le fichier a changé pendant sa lecture ; refaire l'export.")
    table = pd.DataFrame(records).astype({c: "float64" for c in COLUMNS[1:]})
    table["security_id"] = table["security_id"].astype("string")
    table["indicator_end_date"] = pd.Timestamp(end)
    table["source_file"] = source.name
    table["source_sha256"] = digest
    anomalies = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    report = {
        "status": "imported_with_warnings" if issues else "imported",
        "financial_conventions_verified": False,
        "ready_for_backtest": False,
        "source_file": source.name,
        "source_sha256": digest,
        "sheet": sheet,
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "indicator_end_date": end.isoformat(),
        "price_effective_date": None,
        "row_count": len(table),
        "complete_numeric_rows": int(table[list(COLUMNS[1:])].notna().all(axis=1).sum()),
        "blank_rows_skipped": blank_rows,
        "duplicate_identifiers": 0,
        "missing_by_column": {c: int(table[c].isna().sum()) for c in COLUMNS[1:]},
        "anomaly_count": len(anomalies),
        "anomaly_counts": anomalies["code"].value_counts().to_dict(),
        "conventions_pending": PENDING_CONVENTIONS,
    }
    return Snapshot(
        table,
        anomalies,
        report,
        {
            "columns": dictionary,
            "metadata_columns": {
                "source_excel_row": "Numéro de ligne dans Excel",
                "indicator_end_date": (
                    "Fin des intervalles des indicateurs, pas la date du dernier prix"
                ),
                "source_file": "Nom du fichier lu",
                "source_sha256": "Empreinte de la copie lue",
            },
            "conventions_pending": PENDING_CONVENTIONS,
        },
    )


def write_snapshot(snapshot: Snapshot, destination: Path, source: Path) -> None:
    """Publish a complete output directory; never overwrite an earlier import or the source."""
    destination, source = Path(destination).resolve(), Path(source).resolve()
    if destination == source or destination in source.parents:
        raise ImportValidationError("Le dossier de sortie ne doit pas contenir le fichier source.")
    if destination.exists():
        raise ImportValidationError(
            "Ce dossier de sortie existe déjà ; choisir un nouveau dossier."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".wls-import-", dir=destination.parent) as temp:
        staging = Path(temp) / "result"
        staging.mkdir()
        snapshot.table.to_parquet(staging / "snapshot.parquet", index=False)
        snapshot.anomalies.to_csv(staging / "anomalies.csv", index=False, encoding="utf-8-sig")
        for name, value in [
            ("report.json", snapshot.report),
            ("data_dictionary.json", snapshot.dictionary),
        ]:
            (staging / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        staging.rename(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Importer et contrôler un snapshot WLS statique.")
    parser.add_argument("--input", type=Path, required=True, help="Export wls.xlsx local")
    parser.add_argument("--sheet", default="WLSIndexData")
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Nouveau dossier local de sortie"
    )
    args = parser.parse_args()
    try:
        snapshot = load_snapshot(args.input, args.sheet)
        write_snapshot(snapshot, args.output_dir, args.input)
    except (ImportValidationError, OSError, BadZipFile) as exc:
        parser.exit(1, f"Import arrêté : {exc}\n")
    print(
        f"Import terminé : {snapshot.report['row_count']} titres, "
        f"{snapshot.report['complete_numeric_rows']} lignes complètes, "
        f"{snapshot.report['anomaly_count']} anomalies à vérifier.\n"
        f"Sortie : {args.output_dir}\n"
        "Les valeurs restent brutes ; cet export n'est pas encore prêt pour un backtest."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
