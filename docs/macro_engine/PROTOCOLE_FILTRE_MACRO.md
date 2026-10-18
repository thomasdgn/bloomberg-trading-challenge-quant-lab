# Protocole filtre macro sur le backtest — v1.0

Préenregistrement du 18 octobre 2026, branche `research/macro-filter-backtest`, créée depuis `research/macro-conditional-ic` (f18da5c). Ce document, le code de calcul de `research/macro_filter_backtest/` et ses tests synthétiques sont figés par le tag annoté **protocol-filter-v1.0**, poussé AVANT tout calcul de résultat. Au moment du tag, aucun rendement filtré, aucune activation de filtre par date de rééquilibrage et aucun tirage placebo n'a été calculé ; le backtest de base n'a pas été relancé.

Étude exploratoire. Aucune modification de `src/`, aucune règle de portefeuille, aucun ordre, aucune fusion. Toute nouvelle variante après lecture des résultats exigera une version 2 de ce protocole et un nouveau tag.

## 1. Question

Le backtest de quant-lab à cinq semaines aurait-il eu un meilleur ratio d'information contre le WLS si l'exposition au portefeuille avait été réduite de moitié lorsque des étiquettes macro H strictes étaient vraies ? Association historique 2020–2026, sans portée causale.

## 2. Données figées

**Backtest de base.** Celui de l'audit du 16/10/2026 : copie `git archive` de main **440eeff0bb588ea876217e83d060acc5be4ac06e** dans `quant_lab_audit/main`, exécutée par le harnais `reproduce_backtest.py` (`run_backtest` natif de `src/backtest_execution_v2.py`, inchangé). Score combiné existant 0,75 × rang Tail + 0,25 × rang Elastic Net ; horizon et rééquilibrage 5 semaines ; offsets 0 à 4 ; `ElasticNetConfig` par défaut (3 ans, purge 5 semaines, alpha 0,0005, l1_ratio 0,5, min 20 000 lignes d'entraînement, 50 de test) ; profil **sans_stop** de l'audit, **commission 10 pb + slippage 5 pb = 15 pb** ; un fil de calcul.

Le `config/execution_profiles.json` actuel du dépôt (0 pb) et les fichiers actuels `src/backtest_execution_v2.py`, `src/backtest_portfolio_v1.py`, `src/tail_model_v1.py` diffèrent du snapshot audité. Le protocole utilise exclusivement le snapshot audité, conformément à la consigne « mêmes données figées que l'audit ».

Empreintes SHA-256 vérifiées avant exécution (elles figurent aussi dans `config.py`) :

| Fichier du snapshot | SHA-256 |
| --- | --- |
| data/bloomberg/data/prices_10y.csv.gz | 3e6d0622430da341dd21499501de4249cb305f2b8f15a73351eaedb3f124a4fe |
| data/bloomberg/data/volumes_10y.csv.gz | 64d49355ab39398f500c42a21cb8d44210e21ef75fc9a3469bbb1dbe8e945491 |
| data/bloomberg/data/benchmark_10y.csv | 28a043bf49cb7e2e9a0951fd835034814c65b5a3f030296dd36918b099322473 |
| config/execution_profiles.json | 66e5e24c7ef83064a0e077f31f0013e720a0ac3badfed6fbe66b8d01bcf58d0a |
| data/processed/features_weekly_v1.csv.gz | 3d113e4c4967458745cc94259c437029db3ecd516e6cc9a32508b053b56614ac |
| backtest_main/periods.csv (sortie de l'audit) | 1556015c89ddb38f074a9bc14a497a8089a5d10dacd8cebfa5c8ff91cdfe0727 |
| backtest_main/metrics.json | bb502a393bbe2bd0aa2f6f6f439f8b90c49d1cfd741b4989da9096b87857a356 |
| reproduce_backtest.py | 70160c4c2cd56bea905f11383e9329e230d00f0a0b4e0acb556295bb6a72c0e6 |

Les quatre premières empreintes sont celles de `metrics.json` de l'audit. Le panel de features a été recalculé par l'audit et n'y est pas listé : son empreinte est constatée, puis contrôlée indirectement par la reproduction exacte de `periods.csv`. **Ce panel n'est pas celui du test d'IC conditionnel** (62f13e8c…, snapshot du 10/10/2026) ; les deux études ne portent donc pas sur des scores strictement identiques.

`run_base.py` vérifie aussi que chaque `src/*.py` du snapshot a l'empreinte enregistrée par l'audit, relance le backtest natif dans l'environnement Python 3.14.0 de l'audit, puis `compute.py` exige l'égalité de la relance avec `periods.csv` de l'audit (tolérance absolue 1e-12, écart maximal rapporté). En cas d'écart, arrêt sans résultat.

**Étiquettes.** Sorties H strict validées à l'étape 05, `outputs/macro_engine/2026-10-16_H_strict/macro_regimes.csv`, SHA-256 **456ee3ff2d6ad191714ad43931170d4ff0cb82d02db2982ba6f0d3b7362014bb**, issues exclusivement du cache de référence **20261018T143956.868547Z** (D006). Le calcul revérifie SPEC.md et le manifeste du cache via `macro_engine.reference.reference_metadata`, puis le manifeste des étiquettes via `read_labels`. Deux ablations : avec GPR/EPU (`with_news`) et sans (`without_news`). Aucune nouvelle collecte.

**Jointure.** Pour chaque date de rééquilibrage p (colonne `date` du backtest, vendredi nominal), étiquette de la dernière séance NYSE s avec **s < p strictement** : `merge_asof` arrière, `allow_exact_matches=False` (fonction `join_labels` du test d'IC, réutilisée sans modification). Aucune interpolation ; une étiquette inconnue n'est pas remplacée par une valeur antérieure. Contrôle sur chaque ligne : date de décision > date d'étiquette.

## 3. Mécanisme préenregistré

À chaque date de rééquilibrage t d'un offset, on fixe k_t. Rendement de la période :

**r_t = k_t × r_portefeuille,t + (1 − k_t) × r_WLS,t − coût_t**

- r_portefeuille,t = `net_return_5w` de la base (coûts du portefeuille déjà déduits) ; r_WLS,t = `benchmark_return_5w` (même série WLS que la base).
- **k_t = 0,5 si le filtre est actif à t, sinon k_t = 1.**
- **coût_t = 2 × |k_t − k_{t−1}| × 15 / 10 000**, avec k_{−1} = 1 (état de départ = base non filtrée). Le facteur 2 reproduit la définition du notionnel échangé de `calculate_turnover` existant : passer |Δk| d'une poche à l'autre vend |Δk| et achète |Δk|. Le test unitaire vérifie l'égalité avec `calculate_turnover` et le profil audité.

Hypothèses documentées :

1. Les coûts du portefeuille sont appliqués à sa poche proportionnellement à k (k × rendement net). La réduction de poche et la reconstitution du portefeuille au même rééquilibrage ne sont pas fusionnées : approximation.
2. Les deux poches sont remises à (k, 1 − k) à chaque rééquilibrage. Le rééquilibrage dû à la dérive entre poches à k constant n'est pas facturé ; seule la variation de k l'est, conformément à la consigne.
3. Le WLS est supposé détenable sans frais de détention ni erreur de réplication (instrument indiciel hypothétique).
4. Rotation one-way par période = k_t × rotation de la base + |k_t − k_{t−1}|.

## 4. Variantes — liste fermée

| Code | Règle | Statut |
| --- | --- | --- |
| base | k = 1 en permanence | Référence |
| **F1** | STRESS_MARCHE vrai | **Principal, seul décisionnel** |
| F2 | STRESS_MARCHE ou STRESS_CREDIT ou COURBE_INVERSEE vrai | Secondaire |
| F3 | INFLATION_HAUTE ou CHOC_ENERGIE vrai | **Contaminé, indicatif uniquement : choisi après le test d'IC conditionnel** |
| T | k = 0,5 en permanence | Témoin |
| Placebo | 1 000 séries d'activation aléatoires par blocs, même fréquence que F1 par offset | Distribution de référence |

Chaque variante est calculée pour les cinq offsets et les deux ablations. Aucune autre combinaison d'étiquettes, valeur de k, seuil, horizon ou fenêtre n'est testée.

**Étiquette manquante.** Si au moins une étiquette composant un filtre est inconnue à la date d'étiquette retenue, le filtre est inactif (k = 1) à cette date, même si une autre composante est vraie. Ces cas sont comptés par variante, offset et ablation, et listés.

**Information déjà publique avant ce protocole.** Le rapport d'IC conditionnel (tag protocol-ic-v1.0) a publié, à titre descriptif, des effectifs et écarts d'IC pour toutes les étiquettes, y compris celles de F1 et F2. Sur ses dates de prédiction (calendrier cinq semaines du même code, panel différent) : STRESS_MARCHE vrai sur 7 à 13 dates sur 60–61 selon l'offset ; STRESS_CREDIT jamais vrai ; COURBE_INVERSEE vrai sur 22–23 dates. F1 et F2 ne sont donc pas « aveugles » au sens strict ; F3 est explicitement contaminé. Aucune activation n'a été recalculée sur les dates du backtest avant le tag.

## 5. Placebo

Pour chaque ablation et chaque offset, la série d'activation de F1 est décomposée en blocs (suites consécutives de périodes actives). Un tirage placebo permute aléatoirement ces blocs et les place uniformément au hasard (composition uniforme des périodes inactives), avec au moins une période inactive entre deux blocs. Chaque tirage conserve exactement le nombre de périodes actives et la distribution des longueurs de blocs de F1 dans cet offset ; le code vérifie l'égalité des fréquences pour chaque tirage. Un tirage = une série par offset, tirées successivement avec un même générateur NumPy `default_rng`, graine 20261019 combinée à SHA-256(ablation, filtre de référence). Le mécanisme, k et les coûts sont ceux de la section 3.

Statistique : pour chaque tirage, médiane sur les cinq offsets du ratio d'information ; 1 000 tirages. Le 95e percentile est `numpy.quantile(…, 0.95)` (interpolation linéaire). La position d'une variante est la part, en pourcentage, des tirages strictement inférieurs à sa médiane.

Position de F1, F2 et F3 dans le placebo de F1 (seul placebo décisionnel, pour F1). À titre uniquement descriptif, des placebos de même construction appariés aux fréquences de F2 et de F3 sont aussi produits, car le placebo de F1 n'a pas la fréquence de F2 ou de F3 ; ils ne servent à aucune conclusion.

## 6. Mesures

Par variante, offset et ablation, sur les périodes du backtest de base (aucune période retirée) :

- rendement net cumulé Π(1 + r_t) − 1 ; rendement cumulé du WLS ;
- rendement actif : par période a_t = r_t − r_WLS,t ; cumulé en points (richesse − richesse WLS) ; relatif (richesse / richesse WLS − 1) ; moyenne annualisée (× 52/5) ;
- tracking error = écart-type(a_t, ddof = 1) × √(52/5) ;
- **ratio d'information = moyenne(a_t) / écart-type(a_t, ddof = 1) × √(52/5)** (convention de l'audit, sans correction d'autocorrélation) ;
- drawdown relatif maximal : minimum de (richesse relative / maximum courant − 1), richesse initiale 1 incluse, aux dates de rééquilibrage seulement ;
- taux de réussite : part des périodes avec a_t > 0 ;
- rotation moyenne (section 3) ; nombre de périodes filtrées ; coût total des changements de k ; nombre d'étiquettes manquantes ;
- résultats par année civile de la date de décision : nombre de périodes, périodes filtrées, rendement composé, WLS composé, écart, ratio d'information et taux de réussite (descriptifs, effectifs faibles).

Les offsets se chevauchent : ils ne sont jamais additionnés comme des observations indépendantes. Les synthèses utilisent la médiane sur les cinq offsets, avec minimum et maximum.

## 7. Intervalles de confiance F − base

Pour F1, F2, F3 et T, par offset et ablation : bootstrap moving-block apparié sur les périodes (mêmes indices pour F et la base), blocs de **deux périodes** (dix semaines), débuts tirés avec remise parmi les n − 1 possibles, concaténation puis troncature à n ; **10 000 réplications** ; graine 20261020 combinée à SHA-256(ablation, variante, offset). Statistiques : différence de ratio d'information et différence de rendement actif moyen annualisé. Intervalles percentiles à 95 %, bilatéraux, **descriptifs et non corrigés pour la multiplicité** ; ils n'entrent pas dans le critère. Le rendement de chaque période, coût de changement de k compris, est calculé sur la séquence historique avant rééchantillonnage.

## 8. Critère de succès de F1 et conclusion

Pour chaque ablation, notons M(V) la médiane sur les cinq offsets du ratio d'information de la variante V. Le critère est atteint si et seulement si :

1. M(F1) > M(base), **et**
2. M(F1) > M(T), **et**
3. M(F1) > 95e percentile de la distribution placebo de F1 (section 5).

Conclusion :

- critère atteint dans les deux ablations : « apport démontré selon le critère préenregistré » (au sens de ce test historique exploratoire uniquement) ;
- atteint seulement avec GPR/EPU : « fragile » (SPEC.md section 9) ;
- tout autre cas : **« pas d'apport démontré »**.

F2 et F3 sont rapportés avec les mêmes mesures mais ne modifient jamais la conclusion. F3 n'est jamais présenté comme une preuve.

**Remarques mécaniques connues avant résultats.** (a) Pour T, a_t = 0,5 × a_base,t, sauf le coût de 15 pb de la première période : son ratio d'information est donc quasi identique à celui de la base ; T vérifie qu'une simple réduction d'exposition ne change pas le ratio d'information, et la condition 2 est presque redondante avec la condition 1. (b) Un filtre ne change le ratio d'information que via la répartition des rendements actifs de la base entre périodes filtrées et non filtrées, diminuée des coûts de changement de k. (c) Les étiquettes F1–F3 ne dépendent pas de GPR/EPU ; le test d'IC les a trouvées identiques entre ablations sur ses dates, une identité attendue ici aussi et vérifiée dans les sorties. (d) Avec 7 à 13 activations attendues par offset pour F1, la puissance est faible : un échec du critère ne prouve pas l'absence d'effet.

## 9. Sorties

Hors Git, dans `outputs/macro_filter_backtest/` : `base_run/` (relance et manifeste), `results/` (séries par période, mesures par offset et par année, intervalles bootstrap, tirages et synthèse placebo, étiquettes manquantes, `criterion.json`, `manifest.json` avec empreintes), puis `report.html` autonome (Plotly intégré). Le rendu du rapport est ajouté après le tag : il lit les résultats et ne calcule aucune statistique nouvelle. Commité : `docs/macro_engine/RESULTATS_FILTRE_MACRO.md`, avec le tableau principal, la conclusion dérivée uniquement de la section 8 et les limites.

## 10. Verrouillage

Ordre : code et tests synthétiques ; ce protocole ; commit ; tag annoté protocol-filter-v1.0 ; push de la branche et du tag ; vérification du tag distant ; relance de la base ; calcul. `compute.py` refuse de tourner si le tag manque, n'est pas un ancêtre de HEAD, ou si ce document ou l'un des fichiers de calcul diffère de sa version taguée. Les sorties existantes ne sont jamais écrasées.

## 11. Limites connues avant résultats

Biais de la base relevés par l'audit et non corrigés ici : univers conditionné à la disponibilité de la cible future (374 lignes, 43 dates), 1 262 titres d'un snapshot actuel (survivance), rendements en devises locales sans FX historique comparés à un WLS en USD, exécution supposée à la clôture du signal, PnL des ordres à cours limité non remplis compté quand même. Échantillon court (environ 60 périodes par offset, 2020–2026), un seul épisode de marché par régime, variables macro choisies en connaissant l'histoire, délais de publication approximatifs, GPR/EPU sans millésimes certifiés. Le seul test propre reste le test futur prévu par SPEC.md à partir de novembre 2026.
