# Rapport macro — étape 05 et historique des rééquilibrages

Exécution locale le 18 octobre 2026. Branche : `feature/macro-engine`. Code exécuté : **db98f10c63d8b5e49c9af7ef1b0e71630938db67**, arbre propre au lancement. Le commit documentaire suivant ajoute ce rapport. Aucun changement de main, aucune modification de SPEC.md, aucune PR.

## 1. Travail livré

| Fichier | Comportement |
| --- | --- |
| macro_engine/regimes.py | Douze règles de la section 8, dont onze dans H avec GPR/EPU, neuf sans le bloc ; douze dans R descriptif. Étiquettes multiples, percentiles 20/80 en expansion. |
| macro_engine/export.py | Huit fichiers de la section 11 ; provenance, empreintes, variantes explicites, protection du cache et refus d'écraser des sorties existantes. |
| macro_engine/diagnostics.py | HTML autonome avec Plotly intégré : couverture, manquants, courbes des variables et différences quotidiennes, étiquettes, carte des analogues, contributions, sensibilités, variante robuste et sources. |
| macro_engine/run.py | Point d'entrée hors ligne ; H strict produit obligatoirement les deux variantes. H/R descriptifs restent séparés. R strict est refusé selon D003. |
| macro_engine/rebalance_history.py | Ajout D008 séparé du MVP : un seul fichier long pour les analogues de chaque date à quatre semaines, H strict avec/sans GPR/EPU. |

Le chargement conserve le cache unique **20261018T143956.868547Z** et ses vérifications SHA256. Aucune collecte, aucune clé API, aucun entraînement d'Elastic Net, aucune cible future, aucun rendement actif, IC, PnL ou autre évaluation de performance n'a été calculé pour cette livraison. L'audit actions lit les fichiers existants et reconstruit uniquement la couverture hebdomadaire et des features passées ; il n'appelle ni `compute_target`, ni `build_panel`, ni un ajustement de modèle.

Les coefficients numériques de normalisation déjà utilisés (`ddof=0` pour la standardisation, `ddof=1` pour la volatilité) sont maintenant nommés dans config.py, à valeurs identiques. Le catalogue courant du dollar reflète D003 ; le registre de collecte immuable n'est pas modifié. Aucun écart non validé à SPEC.md n'a été introduit.

## 2. Étiquettes de régime

Chaque seuil utilise les valeurs non manquantes de sa variable depuis le début de son échantillon jusqu'à la date de la ligne incluse. Les seuils évoluent en expansion ; les comparaisons 20/80 sont strictes (< ou >). La courbe inversée est définie par T10Y2Y<0. Une égalité au percentile n'active pas l'étiquette. Plusieurs règles peuvent être vraies en même temps.

Le minimum de 1 260 séances reste un filtre des distances : les étiquettes peuvent exister avant cette date. Une variable manquante produit une étiquette inconnue (`NA`), jamais une fausse valeur False. Le chômage non calculable du 11/02/2026 au 05/03/2026 est conservé comme tel. Sans GPR/EPU, les deux étiquettes correspondantes ne sont pas calculées ; après réunion des variantes dans le fichier, leurs cellules restent vides dans l'ablation.

En descriptif, l'historique des valeurs est révisé à la date de requête indiquée par `as_of_date` ; on ne présente pas ces étiquettes historiques comme des signaux stricts connus à l'époque. En strict, les valeurs et seuils de chaque ligne ne dépendent pas des dates suivantes.

Étiquettes vraies au 16/10/2026, sans interprétation :

| Sample | Mode | Ablation | Étiquettes actives |
| --- | --- | --- | --- |
| H | strict | with_news | RESSERREMENT, CHOC_ENERGIE, RISQUE_GEO_ELEVE, INCERTITUDE_ELEVEE |
| H | strict | without_news | RESSERREMENT, CHOC_ENERGIE |
| H | descriptive | with_news | RESSERREMENT, CHOC_ENERGIE, RISQUE_GEO_ELEVE, INCERTITUDE_ELEVEE |
| R | descriptive | with_news | INFLATION_HAUTE, RESSERREMENT, CHOC_ENERGIE, RISQUE_GEO_ELEVE, INCERTITUDE_ELEVEE |

## 3. Exports MVP réellement produits

Chaque répertoire contient : `macro_raw.parquet`, `macro_pit.parquet`, `macro_state_daily.parquet`, `macro_regimes.csv`, `historical_analogues.csv`, `source_registry.csv`, `macro_diagnostics.html`, `run_manifest.json`.

| Exécution | Variantes | Nombre d'analogues | Répertoire local |
| --- | --- | --- | --- |
| 2026-10-16_H_strict | with_news, without_news | with_news: 5; without_news: 5 | C:\Users\degar\.codex\visualizations\2026\10\16\01a1452a-73d3-7e00-b07a-3a2d4fa52c4c\quant-lab-macro\outputs\macro_engine\2026-10-16_H_strict |
| 2026-10-16_H_descriptive | with_news | with_news: 5 | C:\Users\degar\.codex\visualizations\2026\10\16\01a1452a-73d3-7e00-b07a-3a2d4fa52c4c\quant-lab-macro\outputs\macro_engine\2026-10-16_H_descriptive |
| 2026-10-16_R_descriptive | with_news | with_news: 3 | C:\Users\degar\.codex\visualizations\2026\10\16\01a1452a-73d3-7e00-b07a-3a2d4fa52c4c\quant-lab-macro\outputs\macro_engine\2026-10-16_R_descriptive |

Le fichier `macro_raw.parquet` est l'archive des séries courantes du cache, avec rôle explicite `reference_archive_not_a_pit_signal`. Les valeurs CPI/chômage révisées de cette archive ne servent pas au calcul strict. `macro_pit.parquet` contient les observations brutes et leur filiation de disponibilité/millésime ; `macro_state_daily.parquet` contient les transformations effectivement utilisées. Une clôture S&P 500 du 16/10/2026 n'entre pas dans l'état de ce jour : elle n'est utilisable qu'à la séance suivante.

Les sorties quotidiennes portent `date`, `sample`, `mode`, `ablation`, `as_of_date`. Ne jamais joindre les deux ablations en oubliant leur clé. Le contrat pour la future jointure quant-lab exige une date de prédiction strictement postérieure à la date de décision macro. Aucune jointure de prédictions n'est exécutée ici.

Le manifeste enregistre le commit, l'état propre/sale, les empreintes du code, des exigences, des données brutes et des sept autres fichiers, les versions Python/bibliothèques, les paramètres et les centres/échelles/poids. Sa date d'exécution UTC est une provenance au jour civil : à code, environnement, paramètres et date d'exécution identiques, les huit fichiers sont identiques à l'octet dans le test. Changer le jour d'exécution change cette provenance, sans changer les résultats scientifiques.

Les empreintes des sept fichiers référencés par chacun des trois manifestes ont été revérifiées après exécution. Le HTML est autonome, sans CDN. Sa génération Plotly et son contenu sont testés ; le contrôle visuel en navigateur n'a pas pu aboutir car le navigateur de vérification ne pouvait pas atteindre le serveur local. Aucun hébergement ni publication externe n'a été effectué.

## 4. Historique des analogues — ajout D008 validé

La grille demandée est ancrée au vendredi **06/11/2020**, progresse de **quatre semaines calendaires**, et s'arrête à la borne **16/10/2026**. Son dernier vendredi effectif est le **02/10/2026** : la borne du 16/10 n'est pas ajoutée hors grille. L'exécution ponctuelle du 16/10 reste disponible dans les exports MVP ci-dessus.

Règle validée pour les vendredis fermés : dernière séance NYSE précédente, avec conservation des deux dates. La décision figure dans DECISIONS.md, D008 ; SPEC.md est inchangé.

| Vendredi théorique | Date macro utilisée |
| --- | --- |
| 2021-01-01 | 2020-12-31 |
| 2025-04-18 | 2025-04-17 |

Pour chaque requête, le code tronque indépendamment les dates d'observation et les dates de début des millésimes/publications, reconstruit les deux états stricts, estime la normalisation uniquement jusqu'à cette date et recalcule les analogues, leur Mahalanobis et les neuf sensibilités. Il ne découpe pas un résultat historique calculé une fois en 2026. Les limitations D004 des archives GPR/EPU restent applicables ; « strict » avec ce bloc ne devient pas une certification des anciens millésimes.

| Indicateur | Résultat |
| --- | --- |
| Dates de rééquilibrage | 78 |
| Couples date × ablation | 156 |
| Lignes du fichier long, statuts inclus | 744 |
| Lignes d'analogues effectivement sélectionnés | 742 |
| Couples avec exactement 5 analogues | 129 |
| Couples avec 1 à 4 analogues | 25 |
| Couples sans analogue | 2 |
| SHA256 du fichier long | 42b7475f8cdaab54f4f3c64c7005860cf61887dadb19ef96c3b3874d51086194 |

Fichier unique : `C:\Users\degar\.codex\visualizations\2026\10\16\01a1452a-73d3-7e00-b07a-3a2d4fa52c4c\quant-lab-macro\outputs\macro_engine\history\macro_rebalance_analogues_long.csv`. Aucun autre fichier de résultats n'est produit par ce script. Les étiquettes et sorties MVP proviennent du point d'entrée séparé.

Colonnes principales : `rebalance_date` (vendredi théorique), `query_date` (séance réellement utilisée), `sample=H`, `mode=strict`, `ablation`, `rank`, `episode_start`, `episode_end`, `representative_date`, `distance`, `distance_mahalanobis`, `stability_exact`, `stability_episode`, `stability_variants`, contributions et trois variables proches/éloignées, `selected_count`, `status`, cache/empreinte, commit, embargo, horizon et paramètres de sélection. La stabilité est un décompte sur neuf variantes, sans seuil supplémentaire.

Un cas sans analogue reste une ligne de statut avec rang et dates d'épisode vides ; aucun candidat fictif n'est ajouté. Un résultat à moins de cinq épisodes conserve exactement ceux autorisés par la règle q=5 %, séparation douze mois, embargo 365 jours et minimum 1 260 séances.

### Nombre d'analogues par variante

| Ablation | 0 | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| with_news | 1 | 0 | 0 | 0 | 6 | 71 |
| without_news | 1 | 0 | 0 | 3 | 16 | 58 |

### Toutes les dates avec moins de cinq analogues

| Vendredi | Requête NYSE | Ablation | Nombre | Statut |
| --- | --- | --- | --- | --- |
| 2020-12-04 | 2020-12-04 | with_news | 4 | OK |
| 2021-01-01 | 2020-12-31 | with_news | 4 | OK |
| 2021-02-26 | 2021-02-26 | with_news | 4 | OK |
| 2021-09-10 | 2021-09-10 | without_news | 4 | OK |
| 2021-12-03 | 2021-12-03 | with_news | 4 | OK |
| 2021-12-03 | 2021-12-03 | without_news | 4 | OK |
| 2021-12-31 | 2021-12-31 | without_news | 4 | OK |
| 2022-03-25 | 2022-03-25 | without_news | 4 | OK |
| 2022-12-30 | 2022-12-30 | without_news | 4 | OK |
| 2023-01-27 | 2023-01-27 | without_news | 3 | OK |
| 2023-02-24 | 2023-02-24 | without_news | 3 | OK |
| 2023-03-24 | 2023-03-24 | with_news | 4 | OK |
| 2023-03-24 | 2023-03-24 | without_news | 4 | OK |
| 2023-04-21 | 2023-04-21 | without_news | 3 | OK |
| 2023-05-19 | 2023-05-19 | without_news | 4 | OK |
| 2023-06-16 | 2023-06-16 | with_news | 4 | OK |
| 2023-12-29 | 2023-12-29 | without_news | 4 | OK |
| 2024-02-23 | 2024-02-23 | without_news | 4 | OK |
| 2024-03-22 | 2024-03-22 | without_news | 4 | OK |
| 2024-10-04 | 2024-10-04 | without_news | 4 | OK |
| 2024-11-01 | 2024-11-01 | without_news | 4 | OK |
| 2024-11-29 | 2024-11-29 | without_news | 4 | OK |
| 2025-01-24 | 2025-01-24 | without_news | 4 | OK |
| 2025-07-11 | 2025-07-11 | without_news | 4 | OK |
| 2026-02-20 | 2026-02-20 | with_news | 0 | INCOMPLETE_QUERY_STATE |
| 2026-02-20 | 2026-02-20 | without_news | 0 | INCOMPLETE_QUERY_STATE |
| 2026-09-04 | 2026-09-04 | without_news | 4 | OK |

## 5. Profondeur réelle des données actions de quant-lab

Contrôle en lecture seule de deux checkouts, de la copie d'audit du 10/10 et du panel de recherche local. Les dates ci-dessous sont issues des fichiers eux-mêmes, pas de noms tels que « 10y ». Aucun fichier source n'a été modifié. L'inventaire complet, dates, nombres de lignes et empreintes est conservé localement dans `outputs/macro_engine/equity_depth_audit.json`.

| Donnée observée | Première date | Dernière date | Lignes / portée |
| --- | --- | --- | --- |
| Panel hebdomadaire sauvegardé features_weekly_v1.csv.gz, copie d'audit main | 2016-10-07 | 2026-10-02 | 658 764 lignes ; 522 dates ; cible historique 5 semaines |
| Panel de recherche panel.pkl, distinct de la production | 2016-10-07 | 2026-10-02 | 658 764 lignes ; pas une preuve de production |
| Prix actions du checkout macro courant | 2016-10-07 | 2026-10-16 | 1 262 colonnes titres ; 3 661 lignes calendaires brutes |
| Prix actions de l'ancien checkout original | 2016-10-07 | 2026-10-07 | Copie locale plus ancienne ; ne pas confondre avec le checkout macro |
| Prédictions Elastic Net sauvegardées elastic_net_predictions_v1.csv.gz | 2020-11-06 | 2026-08-07 | 70 232 lignes ; ancienne stratégie à cinq semaines |

**Première prédiction Elastic Net effectivement présente dans les fichiers contrôlés : 06/11/2020.** Cette preuve concerne le fichier historique à cinq semaines, pas une prédiction de la nouvelle stratégie à quatre semaines.

Sur les prix/volumes courants, la couverture hebdomadaire reconstruite sans cible future va du **07/10/2016 au 16/10/2026**, soit **524 semaines**, 1 262 colonnes titres et **622 736 prix titre-semaine non manquants** sur 661 288 cellules possibles. Ce n'est pas un panel 4w sérialisé : `data/processed/strategies/final_four_week/features_4w.csv.gz` n'est pas présent dans ce checkout.

Les six features communes deviennent complètes pour au moins un titre le **29/09/2017**. En appliquant uniquement la règle temporelle trois ans d'entraînement + quatre semaines de purge puis le calendrier hebdomadaire, la première date candidate serait **30/10/2020**. C'est une borne théorique liée aux features : aucun ajustement du modèle, contrôle effectif de tous ses seuils d'entraînement ni fichier de prédictions 4w ne permet ici de la qualifier de première prédiction produite. Le 06/11/2020 demandé pour la grille D008 reste inchangé.

**Aucune observation antérieure au 01/01/2016 dans les 28 fichiers datés inspectés.** La plus ancienne date constatée pour les prix et panels actions est le 07/10/2016. Ce constat porte sur les fichiers locaux contrôlés ; il ne prétend pas exclure une archive personnelle externe, un poste d'un coéquipier ou des données non fournies. Les séries macro plus longues ne créent pas de données actions pour leurs anciens épisodes.

### Empreintes des preuves principales

| Preuve | SHA256 |
| --- | --- |
| saved_legacy_5w_panel | 62f13e8cd8ed1ac5a38bf1808ff8b25b026e7922f2860c002ed4276346686ece |
| saved_legacy_elastic_predictions_5w | ae00963ff9732cf3e961f8c5d98b328d5dcec9cba449b608adeb5c161ff45638 |
| saved_research_panel_not_production | ca26818f8302b3f39edf48673a02e73c178168d1ae208391a78155a5c3822419 |
| Prix courants checkout macro | 03645f0028097201b0ec4043a6985ba47d459212b4420ac653276cb13d444a07 |
| Volumes courants checkout macro | bf33c885e6c964831f0d0726b6ee40502bdf06bd95eae589241aad7f2c195280 |

## 6. Tests et vérifications

**170 tests réussis en 196,39 secondes : 52 tests du cœur et 118 tests macro.** Les 35 nouveaux tests couvrent les étiquettes, les exports/CLI et le script historique. `ruff check macro_engine` et `ruff format --check macro_engine` passent sur les 22 fichiers Python.

| Contrôle | Résultat |
| --- | --- |
| Troncature états, étiquettes et analogues | Six dates : 1990-08-15, 2001-09-17, 2008-09-15, 2020-03-16, 2022-02-24, 2026-10-16 ; quatre variantes autorisées pour les étiquettes/analogues ; égalité exacte. |
| D007 | Étiquettes et états identiques à historique réduit ; absence identique d'analogues, sans abaisser le minimum. |
| Percentiles | Expansion uniquement sur le préfixe ; seuils stricts ; égalités et étiquettes multiples testées ; futur modifié sans effet sur le passé. |
| Données manquantes | Étiquette inconnue conservée ; état de requête incomplet signalé dans l'historique. |
| Fichiers exportés | Huit fichiers réellement générés ; empreintes à l'octet identiques entre deux exécutions indépendantes ; manifeste et HTML inclus. |
| Disponibilité et filiation | PIT brut filtré à la requête ; dernière clôture S&P admise le 15/10 pour l'état du 16/10 ; archive raw explicitement séparée. |
| Séparation des espaces | Exports mixtes H/R refusés ; ablations explicites ; ancien dollar absent de toutes les sorties ; R strict refusé. |
| Référence | Protection d'écriture/écrasement ; ancres de cache inchangées ; absence de collecte automatique. |
| Calendrier historique | 78 dates ; intervalle quatre semaines ; deux jours fériés ; borne finale sans ajout hors grille. |
| Historique PIT | Une requête historique confrontée à une reconstruction avec toutes les données puis avec données tronquées ; mêmes classements, distances, stabilités et CSV. |
| Autres invariants section 12 | Disponibilité, absence d'interpolation, pétrole non positif, embargo, épisodes, poids, contributions, normalisation et déterminisme : tests précédents tous conservés et réussis. |

### Commandes de reproduction

```powershell
.venv/Scripts/python.exe -m pytest tests macro_engine/tests -o addopts="" -q --basetemp=../pytest_macro_stage05_review
.venv/Scripts/python.exe -m ruff check macro_engine
.venv/Scripts/python.exe -m ruff format --check macro_engine

.venv/Scripts/python.exe -m macro_engine.run --date 2026-10-16 --sample H --mode strict
.venv/Scripts/python.exe -m macro_engine.run --date 2026-10-16 --sample H --mode descriptive
.venv/Scripts/python.exe -m macro_engine.run --date 2026-10-16 --sample R --mode descriptive
.venv/Scripts/python.exe -m macro_engine.rebalance_history
```

Les destinations par défaut existent désormais et le code refuse de les écraser. Pour une reproduction, utiliser `--output-dir` vers un nouveau répertoire vide pour le MVP et `--output` vers un nouveau fichier pour l'historique. Le cache de référence est local et ignoré par Git ; il doit être présent avec les empreintes approuvées. Aucune dépendance ou version n'a été changée.

## 7. Commits et arrêt demandé

| Commit | Contenu |
| --- | --- |
| e47d016 | Étiquettes en expansion et tests de troncature |
| 3d1fc28 | Exports, diagnostics autonomes, CLI et tests |
| db98f10 | Script historique séparé, calendrier validé D008 et tests |

Seuls les modules macro, leurs tests, DECISIONS.md et ce rapport sont committés. Tous les exports, prix, panels, caches, fichiers de résultats et données brutes restent locaux et ignorés par Git. SPEC.md et le cœur quant-lab restent inchangés. **Arrêt à la fin de l'étape 05. Aucune PR ouverte.**
