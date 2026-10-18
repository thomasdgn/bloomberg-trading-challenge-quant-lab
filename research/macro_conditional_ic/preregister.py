"""Phase A: counts and unconditional dispersion only, never conditional means."""

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from macro_engine import config as macro_cfg
from macro_engine.export import csv_bytes, sha256
from research.macro_conditional_ic import config as cfg
from research.macro_conditional_ic.common import join_labels, read_labels, verify_prepared
from research.macro_conditional_ic.statistics import minimum_detectable_effect


def markdown_table(headers, rows):
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(str(value) for value in row) + " |" for row in rows],
        ]
    )


def power_table(ic: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """Only the standard deviation sees IC values; counts see dates, not ICs."""
    rows = []
    label_names = [
        name
        for name, variable, _ in macro_cfg.REGIME_RULES
        if variable in macro_cfg.SAMPLE_VARIABLES["H"]
    ]
    common = [
        name
        for name, variable, _ in macro_cfg.REGIME_RULES
        if variable in macro_cfg.SAMPLE_VARIABLES["H"] and variable not in ("GPR", "EPU")
    ]
    for score in cfg.SCORES:
        for offset in cfg.OFFSETS:
            sample = ic.loc[ic.score.eq(score) & ic.offset.eq(offset) & np.isfinite(ic.ic)]
            sigma = float(sample.ic.std(ddof=1))  # Entire offset, not a macro partition.
            metadata = sample[["date", "offset"]].copy()  # Deliberately no IC column.
            joins = {
                ablation: join_labels(metadata, labels, ablation) for ablation in cfg.ABLATIONS
            }
            for name in common:
                if not joins["with_news"][name].equals(joins["without_news"][name]):
                    raise ValueError(
                        "Common labels are not identical: preregistered multiplicity is invalid."
                    )
            for ablation, joined in joins.items():
                for name in label_names:
                    if ablation == "without_news" and name not in common:
                        continue
                    flag = joined[name]
                    nt, nf = int(flag.eq(True).sum()), int(flag.eq(False).sum())
                    rows.append(
                        {
                            "score": score,
                            "ablation": ablation,
                            "label": name,
                            "offset": offset,
                            "n_true": nt,
                            "n_false": nf,
                            "n_unknown": int(flag.isna().sum()),
                            "sigma_unconditional": sigma,
                            "mde": minimum_detectable_effect(nt, nf, sigma),
                            "enough_blocks": min(nt, nf) >= cfg.MIN_BLOCKS_PER_GROUP,
                        }
                    )
    return pd.DataFrame(rows)


def main():
    for path in (cfg.PROTOCOL, cfg.SNAPSHOT, cfg.MDE_TABLE):
        if path.exists():
            raise FileExistsError("No silent rewrite of a preregistration.")
    prepared = verify_prepared()
    ic = pd.read_csv(cfg.PREPARED / cfg.IC_FILENAME, parse_dates=["date"])
    labels = read_labels()
    power = power_table(ic, labels)
    cfg.PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
    cfg.MDE_TABLE.write_bytes(csv_bytes(power))
    snapshot = {
        "phase": "A; no conditional means or contrasts computed",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "prepared_sha256": {
            name: sha256((cfg.PREPARED / name).read_bytes())
            for name in (cfg.DATA_FILENAME, cfg.IC_FILENAME, cfg.PREPARED_MANIFEST)
        },
        "labels_sha256": sha256((cfg.LABEL_DIRECTORY / "macro_regimes.csv").read_bytes()),
        "mde_sha256": sha256(cfg.MDE_TABLE.read_bytes()),
        "reference_cache": macro_cfg.REFERENCE_CACHE,
        "reference_manifest_sha256": macro_cfg.REFERENCE_MANIFEST_SHA256,
        "spec_sha256": macro_cfg.SPEC_SHA256,
        "core_commit": cfg.CORE_COMMIT,
        "panel_sha256": cfg.PANEL_SHA256,
        "source_dates": [prepared["date_first"], prepared["date_last"]],
        "parameters": {
            name: getattr(cfg, name)
            for name in (
                "FAMILY_ALPHA",
                "POWER",
                "HYPOTHESES",
                "BLOCK_LENGTH",
                "MIN_BLOCKS_PER_GROUP",
                "BOOTSTRAP_REPLICATES",
                "BOOTSTRAP_SEED",
                "MIN_VALID_BOOTSTRAP_FRACTION",
                "CONSISTENT_OFFSETS",
            )
        },
    }
    cfg.SNAPSHOT.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    text = [
        "# Protocole IC conditionnel — v1.0",
        (
            "Préenregistrement du 18 octobre 2026, branche "
            "research/macro-conditional-ic. Ce document, les 200 lignes de "
            "MDE_IC_CONDITIONNEL.csv, INPUTS_IC_CONDITIONNEL.json, le code et les "
            "tests seront figés par le tag annoté **protocol-ic-v1.0** puis poussés "
            "AVANT toute moyenne d'IC par étiquette. Aucun IC conditionnel n'a été "
            "consulté pendant la rédaction ni le calcul de puissance."
        ),
        "## 1. Question et données fixées",
        (
            "H0 : l'IC moyen est identique quand une étiquette macro est vraie ou "
            "fausse. Contraste bilatéral Δ = moyenne(IC | vrai) − moyenne(IC | faux). "
            "Association historique exploratoire ; aucune causalité, règle de "
            "portefeuille, optimisation, rendement ou ordre n'est testé."
        ),
        (
            "Les archives par titre initiales ne couvrent qu'un offset Elastic Net ; "
            "le score combiné n'est archivé qu'au 02/10/2026 sans cible réalisée. "
            "L'utilisateur a explicitement autorisé le 18/10/2026 la régénération "
            "historique des deux scores avec le code cinq semaines figé, sans "
            "modification de quant-lab. Les IC agrégés de validation ne remplacent "
            "pas les scores combinés manquants."
        ),
        "Panel sauvegardé : features_weekly_v1.csv.gz, "
        f"SHA256 **{cfg.PANEL_SHA256}**. Code cœur figé : **{cfg.CORE_COMMIT}** ; "
        "ses fichiers sont vérifiés avant ajustement. La cible future est lue directement "
        "dans **future_excess_return_5w**, jamais recalculée. "
        "Le module macro n'est pas un prédicteur de rendement.",
        (
            "Régénération : mêmes six features V1, ElasticNetConfig existant (trois "
            "ans, purge cinq semaines, pas cinq semaines, alpha=0,0005, l1_ratio=0,5, "
            "min_train_rows=20 000, min_test_rows=50) ; modèles existants make_model "
            "et make_tail_model ; aucune recherche d'hyperparamètres. Combiné = 0,75 "
            "× rang percentile Tail + 0,25 × rang percentile Elastic Net, rangs "
            "moyens par date et même univers évalué. Les cibles connues ne sont "
            "utilisées qu'en entraînement purgé et pour mesurer l'IC après "
            "prédiction. L'univers historique reste celui de l'ancienne préparation "
            "conditionnée à la disponibilité de la cible ; il n'est pas corrigé dans "
            "cette étude et ne prouve pas l'investissabilité passée."
        ),
        f"Préparation avant le tag : **{prepared['predictions_rows']} lignes titre-date**, "
        f"**{len(ic)} IC inconditionnels** (deux scores × 304 dates), "
        f"du **{prepared['date_first']} au {prepared['date_last']}**. "
        "Les fichiers de données restent dans outputs/macro_conditional_ic/prepared, "
        "ignorés par Git. Leurs empreintes exactes sont dans INPUTS_IC_CONDITIONNEL.json.",
        (
            "Étiquettes : sorties H strict avec/sans GPR/EPU validées à l'étape 05, "
            "issues exclusivement du cache 20261018T143956.868547Z. Source macro, "
            "code, états et percentiles inchangés ; limites PIT_APPROXIMATED et "
            "CONTEMPORARY_INPUT_RETRO_METHOD de GPR/EPU conservées. Les neuf "
            "étiquettes communes aux deux ablations ont été vérifiées identiques sur "
            "les dates retenues ; leurs tests sont donc dupliqués pour présentation, "
            "pas comptés comme preuves supplémentaires."
        ),
        "## 2. Calendrier et jointure stricte",
        (
            "Chaque offset utilise une date toutes les cinq semaines du calendrier V1 "
            "existant : 61 dates pour chacun des offsets 0–3, 60 pour l'offset 4. Le "
            "rendement cible couvre cinq semaines ; les horizons ne se chevauchent "
            "pas à l'intérieur d'un offset. Les cinq offsets se chevauchent entre eux "
            "et ne sont jamais additionnés comme des observations indépendantes."
        ),
        (
            "Pour chaque date nominale de prédiction p, sélectionner la dernière "
            "ligne macro de séance NYSE s avec **s < p**, par jointure as-of arrière "
            "avec allow_exact_matches=False. Aucune jointure de même date, "
            "interpolation ni remplissage d'une étiquette inconnue par une étiquette "
            "antérieure. Conserver macro_date, prediction_date et offset pour audit. "
            "Les vendredis fériés restent les dates nominales des prédictions "
            "hebdomadaires du cœur ; la date macro est une séance strictement "
            "précédente."
        ),
        (
            "IC par date : Spearman entre chaque score et la cible sauvegardée, sur "
            "les mêmes titres complets, rangs moyens en cas d'ex æquo. Un score ou "
            "une cible constante rend l'IC non estimable. Les dates d'IC non fini et "
            "les étiquettes NA sont exclues du contraste concerné, conservées dans le "
            "décompte d'exclusions. Aucun autre filtre ou sous-échantillon n'est "
            "exploré."
        ),
        "## 3. Effet minimal détectable — calcul antérieur aux contrastes",
        (
            "α familial = 5 %, puissance de planification = 80 %, test bilatéral. "
            "Famille fixée à **110** contrastes uniques : deux scores × onze "
            "étiquettes × cinq offsets. Les neuf étiquettes communes répétées dans "
            "l'ablation ne créent pas 90 tests supplémentaires. Bonferroni est fixé "
            "avant résultats ; α par contraste = 0,05/110. Aucune sélection de la "
            "meilleure étiquette ou du meilleur offset."
        ),
        (
            "Pour chaque score et offset, σ est uniquement l'écart-type historique "
            "global des IC inconditionnels (ddof=1), sans partition macro. Pour "
            "chaque étiquette, n_vrai et n_faux sont comptés sur les dates d'IC "
            "valides et d'étiquette connue. Le code de puissance ne joint aux "
            "étiquettes que des dates/offsets : aucune valeur d'IC n'est disponible "
            "dans la table de comptage."
        ),
        (
            "Formule fixée : **MDE = [z(1−α/(2×110)) + z(0,80)] × σ × √[2 × (1/n_vrai "
            "+ 1/n_faux)]**. Le facteur 2 est une inflation de variance fixée pour le "
            "bloc bootstrap de deux observations, sans estimation à partir d'un "
            "contraste. MDE exprimé en points d'IC ; si un effectif est nul ou σ non "
            "positive/non finie : non estimable, données insuffisantes. C'est une "
            "approximation analytique de puissance sous variance homogène et "
            "dépendance courte, pas une garantie de puissance en présence de "
            "dépendance longue. Aucun effet moyen conditionnel n'intervient dans ce "
            "calcul."
        ),
        (
            "Les valeurs numériques complètes ci-dessous sont aussi conservées sans "
            "arrondi dans MDE_IC_CONDITIONNEL.csv, dont l'empreinte est figée. Les "
            "effectifs insuffisants ont également leur MDE calculé si possible, à "
            "titre descriptif uniquement."
        ),
    ]
    text.append(
        markdown_table(
            [
                "Score",
                "Ablation",
                "Étiquette",
                "Offset",
                "n vrai",
                "n faux",
                "NA",
                "σ global",
                "MDE",
                "≥20 dans chaque groupe",
            ],
            [
                [
                    row.score,
                    row.ablation,
                    row.label,
                    row.offset,
                    row.n_true,
                    row.n_false,
                    row.n_unknown,
                    f"{row.sigma_unconditional:.9f}",
                    f"{row.mde:.9f}" if pd.notna(row.mde) else "non estimable",
                    row.enough_blocks,
                ]
                for row in power.itertuples(index=False)
            ],
        )
    )
    text += [
        "## 4. Bootstrap et intervalles — fixés avant calcul conditionnel",
        (
            "Un bloc élémentaire est un résultat à horizon cinq semaines non "
            "chevauchant dans son offset. Seuil de description : **au moins 20 blocs "
            "élémentaires connus dans chacun des groupes vrai ET faux**, dans chaque "
            "offset, pour permettre une interprétation de cet offset. Le "
            "non-chevauchement supprime le recouvrement mécanique des horizons ; il "
            "ne prouve pas l'indépendance économique des observations."
        ),
        (
            "Bootstrap moving-block apparié, séparément par score/étiquette/offset : "
            "blocs contigus de **deux observations** (dix semaines), avec remise "
            "parmi les n−1 débuts possibles ; concaténation puis troncature à n "
            "dates. Les couples (IC, étiquette) sont rééchantillonnés ensemble et les "
            "dates manquantes restent à leur emplacement. Les groupes vrai/faux ne "
            "sont pas rééchantillonnés séparément. Les deux scores et les offsets ne "
            "sont pas réunis dans un échantillon artificiellement agrandi."
        ),
        (
            "**100 000 réplications**, graine de base 20261018, sous-graine "
            "déterministe SHA256(score, étiquette, offset), aucune optimisation de "
            "longueur de bloc. Les réplications sans les deux groupes sont non "
            "estimables ; il faut au moins 99 % de réplications valides pour fournir "
            "l'intervalle. Intervalle bootstrap basic bilatéral aux quantiles "
            "α/(2×110) et 1−α/(2×110), soit **99,954545 % par contraste**, puis "
            "intersection avec les bornes physiques [−2,+2]. La couverture familiale "
            "de 95 % reste approximative car les intervalles bootstrap sont eux-mêmes "
            "estimés. Aucun changement de méthode selon le résultat."
        ),
        "## 5. Règles de conclusion fixées",
        (
            "Par offset : (1) moins de 20 blocs dans l'un des deux groupes, MDE ou "
            "intervalle non estimable : **données insuffisantes**, moyennes seulement "
            "décrites ; (2) sinon, intervalle corrigé excluant zéro : **effet "
            "détecté**, de signe donné par Δ ; (3) sinon, intervalle entièrement "
            "inclus strictement dans [−MDE,+MDE] : **absence d'effet détectable à "
            "l'échelle MDE** ; (4) autres cas : **données insuffisantes**. Un simple "
            "résultat non significatif n'est donc jamais une preuve d'absence. La MDE "
            "n'est pas un seuil qui annule une détection statistique ; le ratio "
            "|Δ|/MDE est rapporté séparément."
        ),
        (
            "Conclusion d'ensemble par score/étiquette/ablation : les cinq offsets "
            "doivent satisfaire la condition d'effectifs et d'estimabilité. **Effet "
            "détecté** si au moins quatre offsets ont un effet détecté de même signe. "
            "**Absence d'effet détectable** si les cinq offsets satisfont la règle "
            "d'absence. Sinon **données insuffisantes**. Le nombre d'offsets de signe "
            "positif/négatif est rapporté, sans les traiter comme cinq études "
            "indépendantes. Aucun agrégat d'effectif ni p-value pooled entre offsets."
        ),
        (
            "Le rapport donne chaque offset : n vrai/faux/NA, IC moyens vrai/faux, Δ, "
            "intervalle corrigé, MDE, |Δ|/MDE et verdict ; puis la cohérence des cinq "
            "offsets. Les cas rares ne sont jamais interprétés, même si une moyenne "
            "ou un intervalle paraît favorable."
        ),
        "## 6. Verrouillage et reproductibilité",
        (
            "Ordre obligatoire : préparer et vérifier les scores ; calculer "
            "uniquement les comptages/σ/MDE ; committer ce protocole, les données de "
            "puissance et le code ; créer le tag annoté protocol-ic-v1.0 ; pousser "
            "branche et tag ; vérifier le tag distant ; ensuite seulement exécuter "
            "infer.py. Le programme d'inférence vérifie l'existence du tag, son "
            "ascendance, l'identité des fichiers de protocole/code et les empreintes "
            "des entrées, avant toute partition numérique de l'IC. Les tests "
            "antérieurs au tag utilisent exclusivement des données synthétiques."
        ),
        (
            "Les sorties de calcul, prédictions par titre, cibles, jointures et "
            "tirages bootstrap restent hors Git. Les documents ne contiennent que "
            "paramètres, empreintes, effectifs et résultats agrégés. Aucun fichier "
            "src/, règle de portefeuille, réglage de modèle ou ordres n'est modifié. "
            "La PR du moteur macro reste sur feature/macro-engine ; cette recherche "
            "demeure sur research/macro-conditional-ic."
        ),
        (
            "Références méthodologiques primaires : [NIST, puissance et taille "
            "d'échantillon](https://www.itl.nist.gov/div898/handbook/prc/section2/prc2"
            "22.htm) ; [NIST, différence de moyennes](https://www.itl.nist.gov/div898/"
            "handbook/prc/section3/prc312.htm) ; [NIST, "
            "Bonferroni](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473."
            "htm) ; [Künsch (1989), bootstrap de séries "
            "stationnaires](https://doi.org/10.1214/aos/1176347265) ; [SciPy, types "
            "d'intervalles bootstrap](https://docs.scipy.org/doc/scipy/reference/gener"
            "ated/scipy.stats.bootstrap.html). Le facteur d'inflation 2 et les règles "
            "de conclusion sont les choix de ce protocole, pas des garanties fournies "
            "par ces références."
        ),
    ]
    cfg.PROTOCOL.write_text("\n\n".join(text) + "\n", encoding="utf-8", newline="\n")
    print(f"Phase A complete: {len(power)} MDE rows; conditional means never computed.")


if __name__ == "__main__":
    main()
