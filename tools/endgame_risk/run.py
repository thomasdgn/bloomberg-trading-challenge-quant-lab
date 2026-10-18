"""CLI: private local reports only. Missing inputs block all risk numbers."""

import argparse
import json
import subprocess
from pathlib import Path

import pandas as pd

from tools.endgame_risk.analytics import attribution, homogeneous, targeted
from tools.endgame_risk.data import DataBlocked, digest, earnings_calendar, load_inputs

ROOT = Path(__file__).resolve().parents[2]


def audit_repository(root):
    data = Path(root) / "data/bloomberg/data"
    findings = []
    if not data.exists():
        return ["Local Bloomberg data directory missing."]
    universe = pd.read_csv(data / "universe.csv")
    prices = pd.read_csv(data / "prices_10y.csv.gz", index_col="date", parse_dates=True)
    covered = float(universe.loc[universe.id.isin(prices.columns), "index_weight"].sum())
    if covered < 1 - 1e-6:
        findings.append(
            f"Full WLS history unavailable: {covered:.6%} of supplied WLS weight covered."
        )
    static = pd.read_csv(data / "static.csv")
    for field in ("currency", "sector", "country", "price_unit_multiplier"):
        missing = len(static) if field not in static else int(static[field].isna().sum())
        if missing:
            findings.append(f"Missing {field}: {missing} metadata rows.")
    fx = pd.read_csv(data / "fx_rates.csv")
    counts = fx.groupby("currency").date.nunique()
    findings.append(f"FX distinct-date counts: {counts.to_dict()}; dated histories required.")
    benchmark = pd.read_csv(data / "benchmark_10y.csv").dropna(subset=["px_last"])
    findings.append(f"Stored WLS index last observation: {benchmark.date.max()} (not a proxy).")
    findings.append(
        "WLS snapshot date, price units and common return convention need verification."
    )
    findings.append(
        "Future earnings dates unavailable: invalid latest_announcement_dt() extraction."
    )
    return findings


def markdown_table(frame):
    def display(value):
        if value is None or pd.isna(value):
            return "indisponible"
        if isinstance(value, float):
            return f"{value:.8f}"
        return str(value).replace("|", "/").replace("\n", " ")

    rows = [
        "| " + " | ".join(map(str, frame.columns)) + " |",
        "| " + " | ".join("---" for _ in frame.columns) + " |",
    ]
    rows += [
        "| " + " | ".join(display(v) for v in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join(rows)


def short_report(destination, payload, table=None, groups=None, top=None, events=None):
    lines = [
        "# Pilotage de fin de challenge — simulation sans ordre",
        "Aucune instruction transmise à un courtier. Aucune performance attendue estimée.",
    ]
    if payload["status"] == "blocked":
        lines += ["**CALCULS BLOQUÉS** — aucun poids réel, TE ou allègement calculé."]
        lines += [f"- {finding}" for finding in payload["blockers"]]
        lines += [
            "Les montants des ordres en attente ne constituent pas des positions exécutées. "
            "Les cashs réservés et disponibles doivent être rapprochés après exécution."
        ]
    else:
        provenance = payload["provenance"]
        lines += [
            f"Date du portefeuille : {provenance['as_of_date']}. "
            f"TE ex ante annualisée : **{payload['annual_te']:.2%}**. "
            f"{provenance['n_weeks']} semaines communes en USD du "
            f"{provenance['first_return']} au {provenance['last_return']}. "
            f"Shrinkage Ledoit-Wolf : {provenance['shrinkage']:.4f}. "
            f"Couverture du poids WLS : {provenance['wls_weight_covered']:.6%}."
        ]
        scenarios = pd.DataFrame(payload["homogeneous"])
        scenarios["violations"] = scenarios.violations.map(lambda v: ", ".join(v) or "aucune")
        lines += [
            "## Leviers homogènes",
            markdown_table(scenarios),
            "×1,5 est une TE théorique : le scénario peut nécessiter des positions négatives. "
            "Aucune faisabilité n'est présumée. Sans règlement fourni, les contraintes "
            "du challenge restent non vérifiées.",
            "## Réduction ciblée",
            "```json\n" + json.dumps(payload["targeted"], indent=2, ensure_ascii=False) + "\n```",
            "Allègements théoriques en fractions de NAV, produit conservé en cash USD ; "
            "aucune quantité ni ordre d'exécution. Une ligne allégée compte pour une "
            "transaction, quelle que soit la taille ; coûts, lots et liquidité non modélisés. "
            "Un objectif peut être impossible avec des ventes seules.",
            "## Quinze premières contributions au risque actif",
            markdown_table(
                top.reset_index()[
                    [
                        "id",
                        "portfolio_weight",
                        "active_weight",
                        "marginal_te",
                        "total_te_contribution",
                        "sector",
                        "country",
                        "currency",
                    ]
                ]
            ),
            "Contributions signées, en points de TE annualisée ; les contributions négatives "
            "sont conservées. Le classement inclut les sous-poids WLS non détenus.",
        ]
        for field, values in groups.items():
            lines += [
                f"## Décomposition — {field}",
                markdown_table(values.rename("total_te_contribution").reset_index()),
            ]
        lines += [
            "## Résultats connus jusqu'au 13 novembre 2026",
            markdown_table(events),
            "Sélection : jusqu'à 15 plus grosses positions actions détenues, hors cash. "
            "Une date absente signifie indisponible dans les sources, jamais absence "
            "de publication. Seuls les événements connus à la date du portefeuille figurent.",
            "Tous les poids actifs et contributions : `contributions.csv`. "
            "Dates de prix/FX de valorisation : `valuation.csv`. "
            "Les empreintes et conventions figurent dans `run_manifest.json`.",
        ]
    (destination / "RAPPORT.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", type=Path)
    parser.add_argument("--market-config", type=Path)
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-subsets", type=int, default=5000)
    args = parser.parse_args(argv)
    destination = args.output_dir.resolve()
    if not destination.is_relative_to((ROOT / "outputs").resolve()):
        parser.error("All private outputs must remain in the ignored repository outputs directory.")
    if destination.exists():
        parser.error("Choose a new output directory: no overwrite.")
    try:
        if args.market_config is None or args.portfolio is None:
            findings = audit_repository(ROOT)
            if args.market_config is None:
                findings.insert(0, "Verified market input configuration not supplied.")
            if args.portfolio is None:
                findings.insert(0, "Executed portfolio not supplied.")
            else:
                declared = json.loads(args.portfolio.read_text(encoding="utf-8"))
                if declared.get("status") != "executed" or declared.get("orders_pending"):
                    findings.insert(0, "Pending orders / unconfirmed executed holdings and cash.")
            raise DataBlocked("\n".join(findings))
        inputs = load_inputs(args.portfolio, args.market_config)
        rules = json.loads(args.rules.read_text(encoding="utf-8")) if args.rules else None
        te, table, groups, top = attribution(
            inputs.weights, inputs.benchmark, inputs.covariance, inputs.metadata
        )
        scenarios = homogeneous(
            inputs.weights, inputs.benchmark, inputs.covariance, inputs.metadata, rules
        )
        target = targeted(
            inputs.weights,
            inputs.benchmark,
            inputs.covariance,
            inputs.metadata,
            max_subsets=args.max_subsets,
            rules=rules,
        )
        events = earnings_calendar(inputs)
        payload = {
            "status": "computed",
            "annual_te": te,
            "homogeneous": scenarios,
            "targeted": target,
            "provenance": inputs.provenance,
        }
        if args.rules:
            payload["rules_sha256"] = digest(args.rules)
    except (DataBlocked, ValueError, KeyError, OSError, TypeError) as exc:
        payload = {"status": "blocked", "blockers": str(exc).splitlines()}
        destination.mkdir(parents=True)
        short_report(destination, payload)
        code = 2
    else:
        destination.mkdir(parents=True)
        table.to_csv(destination / "contributions.csv")
        inputs.valuation.to_csv(destination / "valuation.csv", index=False)
        events.to_csv(destination / "earnings.csv", index=False)
        short_report(destination, payload, table, groups, top, events)
        code = 0
    payload["code_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    payload["tool_sha256"] = {
        path.name: digest(path) for path in sorted(Path(__file__).parent.glob("*.py"))
    }
    payload["declared_input_sha256"] = {
        name: digest(path)
        for name, path in (
            ("portfolio", args.portfolio),
            ("market_config", args.market_config),
            ("rules", args.rules),
        )
        if path is not None and path.is_file()
    }
    payload["covariance_source_sha256"] = digest(ROOT / "src/covariance.py")
    payload["output_sha256"] = {
        path.name: digest(path) for path in sorted(destination.iterdir()) if path.is_file()
    }
    (destination / "run_manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": payload["status"], "report": str(destination / "RAPPORT.md")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
