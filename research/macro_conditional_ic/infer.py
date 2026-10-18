"""Phase B: blocked until the exact preregistration tag exists and is verified."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from macro_engine import config as macro_cfg
from macro_engine.export import code_provenance, csv_bytes, sha256
from research.macro_conditional_ic import config as cfg
from research.macro_conditional_ic.common import (
    guard_preregistered,
    join_labels,
    read_labels,
    verify_prepared,
)
from research.macro_conditional_ic.prepare import cross_section_ic
from research.macro_conditional_ic.preregister import markdown_table
from research.macro_conditional_ic.statistics import (
    conditional_statistics,
    offset_verdict,
    overall_verdict,
)


def deterministic_seed(score, label, offset):
    identity = f"{score}:{label}:{offset}".encode()
    return (cfg.BOOTSTRAP_SEED + int(hashlib.sha256(identity).hexdigest()[:8], 16)) % (2**32)


def compute(predictions, ic, labels, power, *, progress=None):
    schedule = ic[["date", "offset"]].drop_duplicates().sort_values("date")
    # Actual per-title label join, with strict time inequality checked on EVERY row.
    joined_predictions, joins = [], {}
    for ablation in cfg.ABLATIONS:
        joined = join_labels(schedule, labels, ablation)
        joins[ablation] = joined
        paired = predictions.merge(joined, on=["date", "offset"], validate="many_to_one")
        if not paired.date.gt(paired.macro_date).all():
            raise ValueError("A prediction uses a same-day or future macro label.")
        paired["ablation"] = ablation
        joined_predictions.append(paired)
    rows, cache = [], {}
    for specification in power.to_dict("records"):
        score, label, offset = (
            specification["score"],
            specification["label"],
            specification["offset"],
        )
        ablation = specification["ablation"]
        key = score, label, offset
        if key not in cache:
            selected = ic.loc[ic.score.eq(score) & ic.offset.eq(offset)].sort_values("date")
            aligned = selected.merge(
                joins[ablation][["date", "macro_date", label]], on="date", validate="one_to_one"
            )
            stats = conditional_statistics(
                aligned.ic.to_numpy(dtype=float),
                aligned[label].to_numpy(dtype=float, na_value=np.nan),
                seed=deterministic_seed(*key),
            )
            cache[key] = stats
            if progress and len(cache) % 10 == 0:
                progress(len(cache), cfg.HYPOTHESES)
        row = {**specification, **cache[key]}
        if row["n_true"] != specification["n_true"] or row["n_false"] != specification["n_false"]:
            raise ValueError("Counts differ from preregistration.")
        row["mde"] = None if pd.isna(row["mde"]) else float(row["mde"])
        row["ratio_abs_delta_mde"] = (
            abs(row["difference"]) / row["mde"]
            if row["difference"] is not None and row["mde"]
            else None
        )
        row["verdict"] = offset_verdict(row)
        rows.append(row)
    detailed = pd.DataFrame(rows)
    overall = []
    for (score, ablation, label), group in detailed.groupby(
        ["score", "ablation", "label"], sort=False
    ):
        records = group.where(pd.notna(group), None).to_dict("records")
        # Float columns retain NaN through where; normalize before rule application.
        for row in records:
            for name in ("ci_low", "ci_high", "mde", "difference"):
                if pd.isna(row[name]):
                    row[name] = None
        overall.append(
            {
                "score": score,
                "ablation": ablation,
                "label": label,
                "min_n_true": int(group.n_true.min()),
                "min_n_false": int(group.n_false.min()),
                "min_mde": group.mde.min(),
                "max_mde": group.mde.max(),
                **overall_verdict(records),
            }
        )
    return detailed, pd.DataFrame(overall), pd.concat(joined_predictions, ignore_index=True)


def report(detailed, summary, manifest, destination):
    def mde_range(row):
        if pd.isna(row.min_mde) or pd.isna(row.max_mde):
            return "non estimable"
        return f"{row.min_mde:.4f}–{row.max_mde:.4f}"

    text = [
        "# Rapport — test de passage IC conditionnel",
        "Date : 18 octobre 2026. Branche : research/macro-conditional-ic. "
        "PR du moteur macro : "
        "[n°9](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/9), "
        "ouverte sans fusion. Protocole : "
        "[PROTOCOLE_IC_CONDITIONNEL.md](PROTOCOLE_IC_CONDITIONNEL.md), "
        f"tag **{cfg.TAG}**, commit **{manifest['protocol_commit']}**.",
        "## 1. Résultat selon le protocole",
        (
            "La conclusion ci-dessous suit exclusivement les critères figés : 20 "
            "blocs cinq semaines au minimum dans chacun des groupes et chacun des "
            "cinq offsets ; intervalle bootstrap corrigé Bonferroni ; cohérence entre "
            "offsets. Un faible effectif est décrit mais jamais interprété. « Absence "
            "» signifie uniquement absence d'effet détectable à l'échelle MDE "
            "préenregistrée, pas preuve d'un effet exactement nul."
        ),
        markdown_table(
            ["Conclusion d'ensemble", "Nombre de lignes score × ablation × étiquette"],
            [[key, count] for key, count in summary.verdict.value_counts().items()],
        ),
        (
            "Les étiquettes communes aux deux ablations sont des répétitions des "
            "mêmes contrastes. Les nombres de lignes ne constituent pas autant "
            "d'expériences indépendantes ; les offsets se recouvrent entre eux. "
            "Aucune comparaison de rendements ni règle de portefeuille n'est déduite "
            "de ce test."
        ),
        "## 2. Données et traçabilité",
        (
            "Source utilisée après autorisation explicite : scores cinq semaines "
            "régénérés avec le code figé de quant-lab, sans modification du cœur. "
            "Panel sauvegardé et cible future_excess_return_5w lus directement ; le "
            "module macro n'a jamais recalculé de rendement futur. Les anciens "
            "fichiers par titre n'offraient pas les deux scores sur les cinq offsets."
        ),
        f"{manifest['prediction_rows']} prédictions titre-date ; "
        f"{manifest['ic_rows']} IC par date/score ; cinq offsets couvrant les 304 dates "
        "du 06/11/2020 au 28/08/2026. Les deux scores ont été évalués sur les mêmes titres "
        "complets. La régénération garde les paramètres historiques et le mélange de "
        "rangs 75 % Tail / 25 % Elastic Net.",
        "Recalcul de tous les Spearman à partir des scores par titre après le tag : "
        "différence maximale avec la table inconditionnelle de préparation "
        f"**{manifest['max_ic_recalculation_difference']:.3g}**. "
        f"Jointure réelle aux étiquettes : {manifest['joined_prediction_rows']} "
        "lignes titre-date-ablation ; zéro violation de prediction_date > macro_date. "
        "La date macro est la dernière séance strictement antérieure ; aucune étiquette "
        "NA n'est remplacée par sa valeur passée.",
        "Réconciliation globale de préparation avec les archives V1, sans condition macro : "
        f"{json.dumps(manifest['reconciliation'], ensure_ascii=False)}. "
        "Les hashes des données régénérées, du panel, des étiquettes et du tableau MDE "
        "sont figés dans INPUTS_IC_CONDITIONNEL.json. Les sorties détaillées restent "
        f"sous `{destination}` et ne sont pas committées.",
        "## 3. Comparaison par étiquette et cohérence des offsets",
        (
            "Effectifs ci-dessous : minimum parmi les cinq offsets, jamais somme de "
            "dates chevauchantes. Les colonnes +/− donnent le nombre de différences "
            "de signe positif/négatif, à titre descriptif si les effectifs sont "
            "insuffisants."
        ),
        markdown_table(
            [
                "Score",
                "Ablation",
                "Étiquette",
                "min vrai",
                "min faux",
                "Offsets estimables /5",
                "+ / −",
                "MDE min–max",
                "Conclusion",
            ],
            [
                [
                    row.score,
                    row.ablation,
                    row.label,
                    row.min_n_true,
                    row.min_n_false,
                    f"{row.adequate_offsets}/5",
                    f"{row.positive_offsets} / {row.negative_offsets}",
                    mde_range(row),
                    row.verdict,
                ]
                for row in summary.itertuples(index=False)
            ],
        ),
        "## 4. Tous les résultats par offset",
        (
            "IC moyen vrai/faux, écart et MDE en points d'IC. Intervalle basic "
            "moving-block à **99,954545 %**, correction de la famille de 110 "
            "contrastes uniques ; 100 000 réplications, blocs de dix semaines. Les "
            "effectifs sont des horizons élémentaires de cinq semaines non "
            "chevauchants. Les valeurs des lignes sous le seuil de 20 ne sont que "
            "descriptives."
        ),
    ]

    def number(value):
        return "non estimable" if value is None or pd.isna(value) else f"{value:.6f}"

    for (score, ablation), group in detailed.groupby(["score", "ablation"], sort=False):
        text += [
            f"### {score} — {ablation}",
            markdown_table(
                [
                    "Étiquette",
                    "Offset",
                    "n vrai",
                    "n faux",
                    "NA",
                    "IC vrai",
                    "IC faux",
                    "Écart",
                    "IC bas",
                    "IC haut",
                    "MDE",
                    "|Δ|/MDE",
                    "Conclusion",
                ],
                [
                    [
                        row.label,
                        row.offset,
                        row.n_true,
                        row.n_false,
                        row.n_unknown,
                        number(row.ic_true),
                        number(row.ic_false),
                        number(row.difference),
                        number(row.ci_low),
                        number(row.ci_high),
                        number(row.mde),
                        number(row.ratio_abs_delta_mde),
                        row.verdict,
                    ]
                    for row in group.itertuples(index=False)
                ],
            ),
        ]
    text += [
        "## 5. Portée du test et disponibilité du module",
        (
            "Ce test rétrospectif reste exploratoire : variables macro choisies en "
            "connaissant l'histoire, délais approximatifs et archives GPR/EPU sans "
            "anciens millésimes certifiés. Le panel et les modèles cinq semaines "
            "gardent leurs limites historiques, notamment l'univers conditionné à une "
            "cible observée ; ce travail ne corrige ni leur univers, ni leur "
            "exécution, ni leur PnL. Aucune preuve de gain de rendement ne peut être "
            "déduite d'une association d'IC."
        ),
        (
            "Le moteur macro peut être testé immédiatement sur feature/macro-engine, "
            "avec le cache de référence local. Les données et le code de ce test sont "
            "disponibles sur research/macro-conditional-ic. Pour une vraie évaluation "
            "future propre, SPEC.md fixe le départ à novembre 2026. Toute future "
            "modification de génération d'ordres réels reste soumise au mode fantôme "
            "pendant au moins un rééquilibrage et au tableau comparatif "
            "production/nouvelle version validé précédemment. Cette livraison ne "
            "génère ni ne modifie aucun ordre."
        ),
        "## 6. Reproduction et arrêt",
        (
            "```powershell\n.venv/Scripts/python.exe -m "
            "research.macro_conditional_ic.prepare\n.venv/Scripts/python.exe -m "
            "research.macro_conditional_ic.preregister\n# Commit, tag et push "
            "obligatoires avant l’étape suivante.\n.venv/Scripts/python.exe -m "
            "research.macro_conditional_ic.infer\n```"
        ),
        (
            "Les étapes de préparation refusent l'écrasement des données déjà "
            "présentes. Pour reproduire l'inférence sur les fichiers déjà archivés, "
            "choisir un nouveau répertoire --output-dir ; le garde-fou vérifie les "
            "fichiers du tag et les empreintes. Ne pas recréer ni déplacer le tag. "
            "Les dépendances existantes macro suffisent ; aucune dépendance du cœur "
            "n'est modifiée."
        ),
        (
            "Sources méthodologiques et hypothèses de puissance : voir le protocole "
            "préenregistré et ses références NIST/Künsch/SciPy. Aucun paramètre n'a "
            "été choisi d'après les IC conditionnels. **Arrêt demandé. Aucune fusion, "
            "aucune PR de recherche et aucune règle de portefeuille.**"
        ),
    ]
    path = cfg.ROOT / "docs/macro_engine/RAPPORT_IC_CONDITIONNEL.md"
    path.write_text("\n\n".join(text) + "\n", encoding="utf-8", newline="\n")


def main(argv=None):
    # FIRST operation: do not read data or examine conditional contrasts before it.
    protocol_commit = guard_preregistered()
    parser = argparse.ArgumentParser(description="Tagged conditional-IC inference, research only.")
    parser.add_argument("--output-dir", type=Path, default=cfg.OUTPUT / "results")
    args = parser.parse_args(argv)
    destination = args.output_dir.resolve()
    if not destination.is_relative_to((cfg.ROOT / "outputs").resolve()):
        raise ValueError("Research data outputs must remain under the ignored outputs directory.")
    if destination.exists():
        raise FileExistsError("No silent overwrite of results.")
    prepared = verify_prepared()
    predictions = pd.read_parquet(cfg.PREPARED / cfg.DATA_FILENAME)
    saved = pd.read_csv(
        cfg.PREPARED / cfg.IC_FILENAME, parse_dates=["date"], float_precision="round_trip"
    )
    recalculated = []
    for (date, offset), group in predictions.groupby(["date", "offset"]):
        for score in cfg.SCORES:
            recalculated.append(
                {
                    "date": date,
                    "offset": offset,
                    "score": score,
                    "ic": cross_section_ic(
                        group.future_excess_return_5w, group[cfg.SCORE_COLUMNS[score]]
                    ),
                }
            )
    ic = pd.DataFrame(recalculated)
    check = ic.merge(
        saved, on=["date", "offset", "score"], suffixes=("", "_saved"), validate="one_to_one"
    )
    error = float((check.ic - check.ic_saved).abs().max())
    if len(check) != len(saved) or error > 1e-12:
        raise ValueError("Per-title Spearman reconstruction differs from preparation.")
    labels, power = read_labels(), pd.read_csv(cfg.MDE_TABLE, float_precision="round_trip")
    detailed, summary, joined = compute(
        predictions,
        ic,
        labels,
        power,
        progress=lambda n, total: print(f"Tagged bootstrap: {n}/{total}", flush=True),
    )
    destination.mkdir(parents=True)
    for name, frame in (
        ("results_by_offset.csv", detailed),
        ("results_summary.csv", summary),
        ("ic_recalculated.csv", ic),
    ):
        (destination / name).write_bytes(csv_bytes(frame))
    joined.to_parquet(destination / "joined_predictions.parquet", index=False, compression="zstd")
    manifest = {
        "protocol_tag": cfg.TAG,
        "protocol_commit": protocol_commit,
        "execution_date_utc": datetime.now(UTC).date().isoformat(),
        "code": code_provenance(),
        "reference_cache": macro_cfg.REFERENCE_CACHE,
        "prediction_rows": len(predictions),
        "ic_rows": len(ic),
        "joined_prediction_rows": len(joined),
        "max_ic_recalculation_difference": error,
        "reconciliation": prepared["reconciliation"],
        "output_sha256": {
            path.name: sha256(path.read_bytes()) for path in sorted(destination.iterdir())
        },
        "protocol_sha256": sha256(cfg.PROTOCOL.read_bytes()),
        "prepared_sha256": prepared["file_sha256"],
    }
    (destination / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    report(detailed, summary, manifest, destination)
    print(summary.verdict.value_counts().to_dict(), flush=True)


if __name__ == "__main__":
    main()
