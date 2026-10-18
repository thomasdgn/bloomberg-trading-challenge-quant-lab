# Macro Regime Engine, spécification figée v1.0

**Projet** quant-lab, module externe de détection de régimes et d'analogues historiques
**Version** 1.0
**Date de gel** 16 octobre 2026
**Statut** Figée. Validée par Claude et ChatGPT après cinq itérations de conception
**Langage** Python (pandas, numpy, scikit-learn)

---

## 0. Règles pour l'agent de code

1. Cette spécification est figée. Tu ne modifies aucun paramètre, aucune variable, aucune transformation de ta propre initiative.
2. Si un choix est impossible à implémenter tel quel (série indisponible, date de départ différente, format inattendu), tu t'arrêtes, tu l'écris dans `DECISIONS.md` avec la raison et l'alternative proposée, puis tu demandes validation.
3. Toute valeur paramétrable vit dans un seul fichier `config.py`. Aucun nombre magique ailleurs.
4. Tu ne modifies ni le code de l'Elastic Net, ni l'optimiseur, ni la construction du portefeuille. Ce module est indépendant.
5. Un bug de biais d'anticipation est silencieux. Le script tourne, les résultats paraissent crédibles, et tout est faux. Les tests de la section 12 sont donc obligatoires et doivent passer avant toute livraison.

---

## 1. Objectif

Construire un moteur quantitatif qui identifie les régimes macroéconomiques et géopolitiques historiques, afin d'évaluer puis éventuellement d'améliorer la robustesse de quant-lab selon les environnements de marché.

Le moteur répond à trois questions, dans cet ordre.

1. **Similarité historique.** Quels épisodes passés ressemblent le plus à la situation à une date donnée ?
2. **Comportement de la stratégie.** Comment l'IC et les risques de quant-lab varient-ils selon ces régimes ?
3. **Valeur ajoutée.** Le régime apporte-t-il une information exploitable pour les décisions de quant-lab ?

Le MVP couvre la question 1 et prépare la question 2. La question 3 est hors périmètre.

**Premier cas d'usage** état du monde au 16 octobre 2026 et ses cinq analogues historiques.

---

## 2. Principes non négociables

1. **Point-in-time.** Une valeur n'est utilisable à la date t que si sa date de disponibilité est antérieure ou égale à t.
2. **Aucune interpolation.** Une donnée mensuelle reste constante entre deux publications. Elle est propagée vers l'avant à partir de sa date de disponibilité, jamais à partir de sa date de référence.
3. **Aucun raccord silencieux.** Deux séries de méthodologies différentes ne sont jamais collées bout à bout.
4. **Provenance tracée.** Chaque série conserve sa source, sa date de téléchargement, sa couverture, son statut point-in-time et ses limitations.
5. **Reproductibilité.** Mêmes données brutes, mêmes paramètres, mêmes versions de bibliothèques, mêmes sorties au bit près.

---

## 3. Variables d'état

### 3.1 Tableau de référence

| N° | Variable | Source | Identifiant | Fréquence | Transformation | Bloc |
|---|---|---|---|---|---|---|
| 1 | Inflation américaine | FRED et ALFRED | `CPIAUCNS` | Mensuelle | Glissement annuel en pourcentage | Inflation |
| 2 | Chômage américain | FRED et ALFRED | `UNRATE` | Mensuelle | Variation sur 3 mois en points | Croissance |
| 3 | Taux du Trésor à 2 ans | FRED | `DGS2` | Quotidienne | Variation sur 126 séances en points | Monétaire et taux |
| 4 | Pente de la courbe | FRED | `T10Y2Y` | Quotidienne | Niveau en points | Monétaire et taux |
| 5 | Spread de crédit | FRED | `BAA10Y` | Quotidienne | Niveau en points | Crédit et stress |
| 6 | Volatilité réalisée | Prix S&P 500 (export Bloomberg en priorité, yfinance en secours signalé) | Indice S&P 500 | Quotidienne | Écart-type des log-rendements sur 20 séances, annualisé par racine de 252 | Crédit et stress |
| 7 | Pétrole | FRED | `DCOILWTICO` | Quotidienne ramenée en fin de mois | Variation logarithmique sur 12 mois des prix de fin de mois | Énergie |
| 8 | Risque géopolitique | Caldara et Iacoviello (matteoiacoviello.com) | GPR mensuel, version de référence depuis 1985 | Mensuelle | log(1 + GPR) | Géopolitique et incertitude |
| 9 | Incertitude de politique économique | Baker, Bloom et Davis (policyuncertainty.com) | EPU États-Unis, version presse mensuelle | Mensuelle | log(1 + EPU) | Géopolitique et incertitude |
| 10 | Dollar | FRED | `DTWEXBGS` | Quotidienne | Variation logarithmique sur 252 séances | Dollar |

### 3.2 Règles particulières

**Inflation.** On utilise le CPI non désaisonnalisé, quasi jamais révisé. Le glissement annuel neutralise la saisonnalité.

**Taux à 2 ans.** Il remplace les Fed Funds, muets à taux zéro (2009 à 2015, 2020 à 2021). Il capte les annonces de politique monétaire et l'assouplissement quantitatif.

**Pétrole.** Le WTI spot a été négatif le 20 avril 2020. On prend donc la dernière observation valide de chaque mois. Toute valeur de fin de mois inférieure ou égale à zéro lève une erreur explicite et bloque l'exécution. La valeur mensuelle est propagée quotidiennement à partir de sa date de disponibilité.

**Volatilité réalisée.** FRED ne diffuse que dix ans d'historique du S&P 500. La source principale est l'export Bloomberg. Le VIX (`VIXCLS`, depuis 1990) sert uniquement de contrôle de cohérence et n'entre pas dans le vecteur.

**Dollar.** Les indices `DTWEXM` (devises majeures, 1973 à 2019) et `DTWEXBGS` (panier large, depuis 2006) ne mesurent pas le même panier. **Ils ne sont jamais raccordés.** Le dollar n'existe que dans l'échantillon récent (section 4).

**GPR et EPU.** Les articles de presse comptés existaient à l'époque, mais la méthode de construction a été définie après coup. Les observations récentes de l'EPU peuvent être révisées. Chaque téléchargement est archivé avec sa date.

### 3.3 Disponibilité et statut point-in-time

| Variable | Règle de disponibilité | Statut |
|---|---|---|
| Inflation, chômage | Millésime ALFRED en vigueur à t (date de début de validité du millésime). Si l'historique des millésimes manque, délai prudent de 15 jours après la fin du mois pour le CPI et de 7 jours pour le chômage | `PIT_VERIFIED` si millésime ALFRED, sinon `PIT_APPROXIMATED` |
| Taux 2 ans, pente, spread, dollar | Valeur de la séance J utilisable à partir de J + 1 jour ouvré | `PIT_APPROXIMATED` |
| Pétrole | Prix de fin de mois utilisable à partir du premier jour ouvré du mois suivant, plus 1 jour ouvré | `PIT_APPROXIMATED` |
| Volatilité réalisée | Calculée avec les clôtures jusqu'à J, utilisable à partir de J + 1 jour ouvré | `PIT_APPROXIMATED` |
| GPR, EPU | Valeur du mois M utilisable 10 jours calendaires après la fin du mois M | `CONTEMPORARY_INPUT_RETRO_METHOD` |

**Calcul sur millésime.** Pour les séries ALFRED, la transformation (glissement annuel, variation sur 3 mois) est calculée à partir des valeurs du millésime en vigueur à t, et non à partir de la série révisée actuelle.

**Statuts possibles**

| Statut | Signification |
|---|---|
| `PIT_VERIFIED` | Valeur et date de disponibilité historiques vérifiées |
| `PIT_APPROXIMATED` | Reconstruction avec un délai prudent documenté |
| `CONTEMPORARY_INPUT_RETRO_METHOD` | Données d'époque, méthode de construction définie après coup |
| `RETROSPECTIVE` | Série entièrement reconstruite après les événements |

---

## 4. Deux échantillons distincts

| Échantillon | Code | Variables | Blocs | Début |
|---|---|---|---|---|
| Historique étendu | `H` | Variables 1 à 9 | 6 | Première date où les 9 variables sont disponibles et transformables (attendue autour de début 1987, déterminée automatiquement) |
| Récent enrichi | `R` | Variables 1 à 10 | 7 | Première date où les 10 variables sont disponibles et transformables (attendue autour de 2007, déterminée automatiquement) |

**Règle absolue.** Les distances de `H` et de `R` sont calculées dans des espaces différents. Elles ne sont jamais mélangées, comparées entre elles, ni fusionnées dans un même classement. Chaque sortie porte la colonne `sample`.

---

## 5. Convention temporelle

1. **Date de décision t.** Photographie de l'information disponible à 23 h 59 UTC le jour t.
2. **Usage.** Le vecteur d'état de t ne peut servir qu'aux décisions prises lors des séances postérieures à t.
3. **Calendrier.** Jours ouvrés américains (calendrier NYSE) pour le moteur quotidien.
4. **Propagation.** Chaque variable est propagée vers l'avant depuis sa date de disponibilité jusqu'à la disponibilité suivante.

---

## 6. Normalisation

1. Les transformations asymétriques (log du GPR et de l'EPU) sont appliquées avant standardisation.
2. **Standardisation à la date t.** Pour chaque variable j, la moyenne et l'écart-type sont estimés sur toutes les observations du vecteur d'état allant du début de l'échantillon jusqu'à t inclus.
3. **Mêmes paramètres pour tous.** Le vecteur de t et tous les vecteurs candidats s antérieurs sont standardisés avec ces mêmes paramètres.
4. **Historique minimal.** Aucune distance n'est produite pour une date t disposant de moins de 5 ans (1 260 séances) d'observations complètes.
5. **Variante de sensibilité.** Standardisation robuste par médiane et écart interquartile. Elle ne remplace pas la méthode principale.

**Valeur des candidats selon le mode**

| Mode | Valeur du candidat s |
|---|---|
| Strict | Vecteur point-in-time tel qu'il était connu à la date s |
| Descriptif | Vecteur calculé sur les données les plus récentes disponibles à t (séries révisées autorisées, signalées) |

---

## 7. Distance et sélection des analogues

### 7.1 Distance principale

Distance euclidienne pondérée sur variables standardisées. Pour une date t et un candidat s, la distance est la racine carrée de la somme, sur les variables j, de w_j multiplié par le carré de (Z de t pour j moins Z de s pour j).

**Pondération par blocs.** Chaque bloc reçoit un poids total identique, égal à 1 divisé par le nombre de blocs (6 pour `H`, 7 pour `R`). Les variables d'un même bloc se partagent son poids à parts égales. La somme des poids vaut 1.

| Bloc | Variables | Poids dans `H` | Poids dans `R` |
|---|---|---|---|
| Inflation | 1 | 1/6 | 1/7 |
| Croissance | 2 | 1/6 | 1/7 |
| Monétaire et taux | 3, 4 | 1/12 chacune | 1/14 chacune |
| Crédit et stress | 5, 6 | 1/12 chacune | 1/14 chacune |
| Énergie | 7 | 1/6 | 1/7 |
| Géopolitique et incertitude | 8, 9 | 1/12 chacune | 1/14 chacune |
| Dollar | 10 | absent | 1/7 |

### 7.2 Distance de comparaison

Distance de Mahalanobis régularisée (estimateur Ledoit-Wolf de scikit-learn), avec une covariance estimée uniquement sur les vecteurs standardisés disponibles jusqu'à t. Elle est produite en parallèle, jamais à la place de la distance principale.

### 7.3 Candidats éligibles

Un candidat s est éligible si toutes les conditions suivantes sont remplies.

1. s est antérieure à t d'au moins 365 jours calendaires (embargo qui exclut l'épisode en cours).
2. Le vecteur de s est complet pour toutes les variables de l'échantillon.
3. s plus l'horizon d'évaluation h reste antérieur à t. Par défaut h vaut 25 séances (environ 5 semaines, horizon documenté de quant-lab). **À vérifier dans le code de quant-lab et à reporter dans `config.py`.**

### 7.4 Construction des épisodes

1. Calculer la distance de t à tous les candidats éligibles.
2. Retenir les candidats sous le seuil q, défini comme le quantile à 5 % des distances.
3. Regrouper en un même épisode les candidats retenus séparés de moins de 20 séances.
4. Représenter chaque épisode par sa date de distance minimale.
5. Imposer une séparation minimale de 12 mois entre deux représentants. En cas de conflit, garder le plus proche.
6. Conserver les 5 épisodes les plus proches.

**Sensibilité obligatoire.** Séparation de 6, 12 et 24 mois. Seuil q à 2,5 %, 5 % et 10 %. Le rapport indique si les 5 analogues restent stables.

### 7.5 Explicabilité

Pour chaque analogue, la contribution de chaque variable est égale à son terme pondéré divisé par la distance au carré. La somme des contributions vaut 1. Les trois variables qui rapprochent le plus et les trois qui éloignent le plus sont exportées.

---

## 8. Étiquettes de régime

1. Étiquettes multiples, non exclusives. Une date peut porter plusieurs étiquettes ou aucune.
2. Seuils calculés sur la distribution du passé disponible à t (percentiles en expansion).
3. Seuils figés à 20 % et 80 %.

| Étiquette | Règle |
|---|---|
| `INFLATION_HAUTE` | Inflation au-dessus du 80e percentile |
| `INFLATION_BASSE` | Inflation sous le 20e percentile |
| `RALENTISSEMENT` | Variation du chômage au-dessus du 80e percentile |
| `RESSERREMENT` | Variation du taux à 2 ans au-dessus du 80e percentile |
| `ASSOUPLISSEMENT` | Variation du taux à 2 ans sous le 20e percentile |
| `COURBE_INVERSEE` | Pente inférieure à zéro |
| `STRESS_CREDIT` | Spread de crédit au-dessus du 80e percentile |
| `STRESS_MARCHE` | Volatilité réalisée au-dessus du 80e percentile |
| `CHOC_ENERGIE` | Variation du pétrole au-dessus du 80e percentile |
| `RISQUE_GEO_ELEVE` | GPR au-dessus du 80e percentile |
| `INCERTITUDE_ELEVEE` | EPU au-dessus du 80e percentile |
| `DOLLAR_FORT` | Variation du dollar au-dessus du 80e percentile (échantillon `R` uniquement) |

---

## 9. Modes d'exécution

| Mode | Usage | Données autorisées |
|---|---|---|
| Descriptif | Comprendre l'histoire, chercher des analogues | Toutes les séries documentées, y compris révisées, signalées comme telles |
| Strict | Toute évaluation financière future | Uniquement les valeurs point-in-time selon la section 3.3 |

**Ablation obligatoire en mode strict.** Chaque exécution stricte produit deux versions, avec et sans GPR et EPU (le bloc géopolitique est alors retiré et les poids des autres blocs renormalisés). Un résultat qui n'existe qu'avec GPR et EPU est marqué fragile.

---

## 10. Architecture du code

```
macro_engine/
    config.py           paramètres figés, identifiants, délais, seuils, poids
    collect.py          téléchargement FRED, ALFRED, GPR, EPU, lecture export Bloomberg
    cache/              données brutes horodatées, jamais modifiées
    pit.py              dates de disponibilité, millésimes, statuts point-in-time
    transform.py        transformations de la section 3
    state.py            vecteurs d'état quotidiens par échantillon et par mode
    normalize.py        standardisation de la section 6
    analogues.py        distances, éligibilité, épisodes, contributions
    regimes.py          étiquettes de la section 8
    export.py           fichiers de la section 11
    diagnostics.py      rapport HTML de qualité des données
    run.py              point d'entrée en ligne de commande
    tests/              tests de la section 12
DECISIONS.md            écarts à la spécification, validés un par un
SPEC.md                 ce document
```

**Dépendances** pandas, numpy, scikit-learn, pyarrow, requests, openpyxl, pandas-market-calendars, plotly, pytest. Versions figées dans `requirements.txt`.

**Clé FRED** lue dans la variable d'environnement `FRED_API_KEY`, jamais écrite dans le code.

**Point d'entrée** `python -m macro_engine.run --date 2026-10-16 --sample H --mode strict`

---

## 11. Fichiers de sortie

| Fichier | Contenu |
|---|---|
| `macro_raw.parquet` | Séries brutes, source, date de téléchargement |
| `macro_pit.parquet` | Observations avec date de référence, date de disponibilité, millésime, statut |
| `macro_state_daily.parquet` | Vecteurs d'état quotidiens, colonnes `date`, `sample`, `mode`, une colonne par variable |
| `macro_regimes.csv` | `date`, `sample`, `mode`, une colonne booléenne par étiquette |
| `historical_analogues.csv` | `query_date`, `sample`, `mode`, `rank`, `episode_start`, `episode_end`, `representative_date`, `distance`, `distance_mahalanobis`, contributions par variable, trois variables qui rapprochent, trois qui éloignent, indicateur de stabilité |
| `source_registry.csv` | Variable, source, identifiant, couverture, fréquence, transformation, règle de disponibilité, statut, limitations |
| `macro_diagnostics.html` | Couverture, valeurs manquantes, ruptures, graphiques des variables, carte des analogues, résultats de sensibilité |
| `run_manifest.json` | Date d'exécution, paramètres, versions des bibliothèques, empreinte des données brutes, identifiant de commit |

**Format de jointure avec quant-lab.** `macro_regimes.csv` et `macro_state_daily.parquet` sont indexés par date de décision t. La jointure avec les prédictions de l'Elastic Net se fait sur la date de prédiction, en vérifiant que la date de prédiction est postérieure à t.

---

## 12. Tests obligatoires

| Test | Vérification | Critère de réussite |
|---|---|---|
| **Troncature** | Calculer le vecteur d'état, les étiquettes et les analogues d'une date t avec toutes les données, puis avec des données coupées à t | Résultats strictement identiques, pour les dates 1990-08-15, 2001-09-17, 2008-09-15, 2020-03-16, 2022-02-24 et 2026-10-16 |
| Disponibilité | Aucune valeur utilisée avant sa date de disponibilité | Zéro violation sur tout l'historique |
| Interpolation | Une variable mensuelle est constante entre deux publications | Zéro valeur intermédiaire |
| Pétrole | Une fin de mois négative ou nulle injectée dans les données | Erreur explicite levée |
| Séparation des échantillons | Aucune distance de `H` dans un classement de `R`, et inversement | Zéro mélange |
| Raccord dollar | `DTWEXM` absent de toutes les sorties | Zéro occurrence |
| Embargo | Aucun analogue à moins de 365 jours de t | Zéro violation |
| Séparation des épisodes | Écart entre représentants supérieur ou égal au paramètre choisi | Zéro violation |
| Poids | Somme des poids égale à 1 pour chaque échantillon et chaque variante d'ablation | Égalité à 1e-12 près |
| Contributions | Somme des contributions égale à 1 pour chaque analogue | Égalité à 1e-9 près |
| Déterminisme | Deux exécutions identiques | Empreintes des sorties identiques |
| Normalisation | Les paramètres de standardisation de t n'utilisent aucune date postérieure à t | Zéro violation |

---

## 13. Hors périmètre du MVP

1. Toute modification du portefeuille, de l'Elastic Net ou de l'optimiseur.
2. Les blocs régionaux zone euro et Chine (version 2).
3. La couche qualitative des ruptures structurelles et technologiques (version 3).
4. L'utilisation d'un LLM dans le calcul. Les IA interviennent uniquement pour expliquer et contester les analogues, après le calcul.

### Phase suivante, IC conditionnel (pour information)

1. IC de Spearman entre le score prédit par l'Elastic Net et le rendement réalisé sur l'horizon h, cohérent avec la cible d'entraînement.
2. Analyse principale sur des dates échantillonnées toutes les 25 séances (horizons non chevauchants). Analyse quotidienne avec bootstrap par blocs en vérification.
3. Effet minimal détectable calculé avant le test.
4. Un régime comptant moins de 20 blocs indépendants est décrit, jamais interprété.
5. Hypothèse nulle. Le régime n'apporte aucune information sur l'IC futur.

---

## 14. Préenregistrement

1. Cette spécification est datée du 16 octobre 2026 et archivée avec son empreinte.
2. Les analyses historiques sont exploratoires, car les variables ont été choisies en connaissant l'histoire.
3. **Le seul test réellement propre est le test futur à partir de novembre 2026.** Ses résultats sont archivés avant d'être connus et conservés séparément des analyses historiques.

---

## 15. Journal des décisions de conception

| Décision | Raison |
|---|---|
| Brent remplacé par WTI de fin de mois | Le Brent commence en 1987, le WTI quotidien a été négatif en avril 2020 |
| Fed Funds remplacés par le taux à 2 ans | Les Fed Funds sont muets à taux zéro |
| CPI non désaisonnalisé | Révisions quasi nulles, point-in-time plus simple |
| Volatilité réalisée sur prix Bloomberg | FRED limite l'historique du S&P 500 à dix ans |
| Dollar seulement dans l'échantillon `R` | `DTWEXM` et `DTWEXBGS` ne mesurent pas le même panier |
| Distance euclidienne pondérée en principal | Mahalanobis dépend d'une covariance instable sur plusieurs décennies |
| Épisodes séparés de 12 mois | Un régime dure souvent 12 à 24 mois, 90 jours produisait des doublons |
| Statut spécifique pour GPR et EPU | Données contemporaines, méthode définie après coup |
| Préenregistrement et test futur | Le choix des variables est lui-même contaminé par la connaissance de l'histoire |

---

## 16. Consignes de démarrage

**Pour l'agent qui construit le code**

> Lis SPEC.md en entier avant d'écrire du code. Construis le module macro_engine dans l'ordre des sections 10 et 11, en commençant par config.py et collect.py. Écris les tests de la section 12 au fur et à mesure, en commençant par le test de troncature. Ne modifie aucun paramètre figé. Tout écart va dans DECISIONS.md et attend ma validation. Avant de déclarer le travail terminé, exécute l'ensemble des tests et donne-moi les cinq analogues du 16 octobre 2026 pour l'échantillon H en mode strict, avec leurs contributions.

**Pour l'agent qui relit le code (l'autre outil)**

> Lis SPEC.md puis le module macro_engine. Ta seule mission est de chasser les fuites d'information future. Pour chaque fonction qui manipule des dates, vérifie qu'aucune valeur postérieure à la date de décision ne peut être utilisée, y compris via une normalisation, un percentile, un remplissage vers l'avant, une jointure ou un calendrier. Liste chaque risque avec le fichier, la ligne, un scénario concret de fuite et un test qui la détecterait. Ne propose aucune autre amélioration.
