# Rapport macro — étape 02 : collecte et traçabilité

**18 octobre 2026 — feature/macro-engine uniquement.**

## Résultat et périmètre

**Collecte brute réelle réussie pour les dix séries.** Les sources sont téléchargées à nouveau depuis le code committé, les millésimes ALFRED sont archivés et le registre des sources est produit.

Cette livraison s'arrête à config.py, collect.py, au cache horodaté, au registre et aux tests de collecte. Aucune transformation macro, date de disponibilité matérialisée, normalisation, état quotidien, étiquette, analogue ou IC n'est implémenté. Aucun ordre ni portefeuille n'est modifié.

**Un conflit de disponibilité est bloquant pour le futur usage strict du dollar : la règle J+1 de la spec ne correspond pas à la publication hebdomadaire H.10.** Il est inscrit dans DECISIONS.md, décision D003, sans substitution de règle ou de série.

## 0 bis — Production et journal des transactions

### Attribution des ordres du 16 octobre

**Attribution à 1bda389 non confirmée : aucun tag live/2026-10-16 créé ou poussé.**

Les recherches locales dans le dépôt et ses sorties n'ont retrouvé aucun execution_orders.csv, final_allocation_explained.csv ou run_manifest.json correspondant à un run de production du 16 octobre. Les résultats et journaux retrouvés sont ceux de recherches, d'audits ou de démonstrations.

Le commit 1bda389 est daté du 16/10/2026 à 23:45:44 heure de Paris. Sa date et le nom de la pipeline ne suffisent pas à attribuer des ordres réels à ce code. L'unique achat précédemment décrit a été déclaré discrétionnaire.

Pour confirmer une attribution, il manque :

1. Le fichier réellement utilisé pour la décision et son empreinte.
2. Le manifeste ou journal du run, avec le commit exact, les paramètres et les dates des données.
3. Le lien entre ce run, la décision humaine et l'exécution réelle.

Le collecteur macro produit désormais son propre manifeste avec commit, état propre/sale et empreintes du code et des données. Cela n'établit pas rétrospectivement la provenance des ordres d'octobre.

### Format proposé pour le journal réel

Le format a été montré dans le chat. **Aucun fichier de transactions réelles ou modèle de journal n'est committé.** Une ligne devra correspondre à une exécution effective, avec quantité exécutée et frais confirmés, sans calculer une quantité à partir d'un montant approximatif. La provenance doit distinguer décision discrétionnaire et modèle ; le commit est non applicable à une décision purement discrétionnaire.

## 1. Décisions validées et configuration

- **D001 validée** : h = quatre semaines, stratégie final_four_week. Commentaire explicite sur l'embargo de 365 jours, qui rend la condition 7.3.3 redondante à cet horizon. Pas de conversion implicite en vingt séances.
- **Future phase IC** : le moteur macro ne recalcule jamais le rendement futur. Il lit future_excess_return_4w dans quant-lab, ou future_excess_return_5w pour l'ancien chemin. Ces noms sont enregistrés dans config.py ; aucune évaluation n'est encore effectuée.
- **D002 validée** : macro_engine/requirements.txt séparé ; **47 versions directes et transitives figées**, installées et importées sous **Python 3.14.0**.
- Aucune modification des exigences racine ou de la CI. Aucun fichier de l'Elastic Net, du risque, du portefeuille ou de l'exécution modifié.

Fichiers du module :

| Fichier | Fonction |
|---|---|
| macro_engine/config.py | Paramètres figés, dix séries, sources, règles décrites, décisions validées et limitations connues |
| macro_engine/collect.py | Téléchargements, pagination, lecture des formats officiels, cache et registre |
| macro_engine/requirements.txt | Dépendances isolées, toutes épinglées |
| macro_engine/tests/test_collect.py | Douze tests ciblant les frontières de collecte et la traçabilité |

Les dépendances principales sont pandas 3.0.6, numpy 2.5.3, scikit-learn 1.9.1, pyarrow 25.0.1, requests 2.34.2, openpyxl 3.1.5, pandas-market-calendars 5.5.0, plotly 7.1.0, pytest 9.1.1 et ruff 0.16.10. yfinance 1.7.0 sert au secours S&P 500 prévu par la spec. xlrd 2.0.2 lit le classeur GPR officiel .xls. La liste complète fait foi dans macro_engine/requirements.txt.

## 2. Collecte finale exécutée

Commande, dans l'environnement macro et avec FRED_API_KEY définie localement :

~~~text
python -m macro_engine.collect
~~~

La clé est lue uniquement dans l'environnement du processus. Pour cette exécution, la variable utilisateur Windows a été transmise au processus sans affichage de sa valeur. Pas de clé dans le code, les URLs enregistrées, les erreurs, le cache ou Git.

La sortie finale est limitée au cache ignoré :

    macro_engine/cache/20261018T143956.868547Z/

- Début du téléchargement UTC : **2026-10-18T14:39:56.868547+00:00**.
- Commit exact du collecteur : **de94172ff3db633583078a801c3f7fc045fb6d34**.
- Dépôt propre au démarrage : **oui**. Code modifié pendant la collecte : **non**.
- Artefacts sources archivés et vérifiés : **14**.
- SHA-256 de source_registry.csv : **0f6338dc061df3fd068a181deb539c140e8ded075acf6895e9a936fb9510b39f**.

Chaque exécution crée un nouveau répertoire UTC, sans écrasement. Les fichiers sont ouverts en création exclusive. Les réponses HTTP d'origine sont conservées avec empreinte et métadonnées de requête expurgées de la clé. Pour Yahoo, l'archive brute est le DataFrame livré par yfinance, sérialisé avant sélection de Close ; ce n'est pas une capture de la réponse HTTP originale.

Les versions lisibles par le futur traitement sont des Parquet de dates et valeurs brutes, avec manquants conservés. Elles ne sont ni transformées ni propagées. Pour ALFRED, les intervalles realtime_start/realtime_end sont conservés ; aucune révision actuelle ne remplace une ancienne valeur dans cette archive.

### Couverture des dix entrées

Dates ci-dessous = dates de référence des observations non manquantes, **pas dates de publication ou de disponibilité**. N compte les valeurs présentes. Les dates mensuelles sont celles de référence de la source ; les données ne deviennent pas disponibles artificiellement au premier du mois.

| Entrée | Source effectivement utilisée | Première date | Dernière date | N observations | Lignes manquantes conservées |
|---|---|---|---|---:|---:|
| CPIAUCNS | FRED/ALFRED | 1913-01-01 | 2026-09-01 | 1,364 | 1 |
| UNRATE | FRED/ALFRED | 1948-01-01 | 2026-09-01 | 944 | 1 |
| DGS2 | FRED | 1976-06-01 | 2026-10-15 | 12,590 | 553 |
| T10Y2Y | FRED | 1976-06-01 | 2026-10-16 | 12,591 | 553 |
| BAA10Y | FRED | 1986-01-02 | 2026-10-15 | 10,197 | 444 |
| SP500 | Yahoo Finance ^GSPC, secours Bloomberg explicitement signalé | 1927-12-30 | 2026-10-16 | 24,816 | 0 |
| DCOILWTICO | FRED | 1986-01-02 | 2026-10-14 | 9,523 | 1,117 |
| GPR | Caldara/Iacoviello | 1985-01-01 | 2026-09-01 | 501 | 0 |
| EPU | Baker/Bloom/Davis | 1985-01-01 | 2026-09-01 | 501 | 0 |
| DTWEXBGS | FRED | 2006-01-02 | 2026-10-09 | 5,208 | 212 |

S&P 500 correspond ici aux **prix de clôture de l'indice**, pas encore à la volatilité réalisée sur vingt séances. Le WTI est encore quotidien ; la sélection de fin de mois et la transformation sur douze mois appartiennent à l'étape suivante. Aucune valeur brute de pétrole n'est supprimée pour simuler ce futur contrôle mensuel.

Le fichier source_registry.csv contient aussi variable, identifiant, bloc, fréquence, transformation prévue, règle de disponibilité décrite, statut PIT, limitations, comptages, fichiers et empreintes, ainsi que le drapeau pit_rule_requires_decision. availability_applied reste False pour les dix séries.

### Millésimes ALFRED

Le nombre de millésimes est obtenu par l'API officielle series/vintagedates. Il n'est ni estimé à partir de la fréquence, ni confondu avec le nombre de lignes de valeurs. Les archives de valeurs sont récupérées par series/observations, output_type=1, sur toute la période de temps réel disponible jusqu'à la collecte.

| Série | Millésimes disponibles | Plus ancien | Plus récent | Lignes d'observations / intervalles archivées |
|---|---:|---|---|---:|
| CPIAUCNS | 932 | 1949-03-24 | 2026-10-14 | 2,526 |
| UNRATE | 800 | 1960-03-15 | 2026-10-02 | 2,199 |

Les dates distinctes de début de validité des archives correspondent aux comptes de millésimes : 932 pour CPIAUCNS et 800 pour UNRATE. Les dates de référence antérieures au plus ancien millésime ne prouvent pas une disponibilité historique à ces dates anciennes. La transformation par millésime n'est pas encore implémentée.

### GPR et EPU : automatisation confirmée

**Oui, les deux téléchargements officiels sont automatisables et ont réussi pendant cette exécution.**

- GPR : fichier Excel 97-2003 de Caldara/Iacoviello, colonne GPR de référence, depuis 1985. Les autres colonnes historiques ou variantes ne sont jamais substituées.
- EPU : fichier officiel US Policy Uncertainty, feuille Main News Index, colonne News_Based_Policy_Uncert_Index, depuis 1985. La feuille Legacy Three Component EPU et la partie pré-1985 ne sont pas raccordées.
- La seule ligne EPU non observationnelle supprimée du tableau de lecture est la ligne de crédit explicitement reconnue de l'éditeur, dont les champs Month et valeur sont vides. Le classeur brut reste intact. Les lignes malformées non reconnues provoquent une erreur ; elles ne sont pas éliminées silencieusement.

Sources : [GPR](https://www.matteoiacoviello.com/gpr.htm), [EPU mensuel US](https://www.policyuncertainty.com/us_monthly.html).

## 3. Statut point-in-time et décisions requises

### CPIAUCNS et UNRATE

Les archives ALFRED permettent de reconstruire les valeurs en vigueur à une date passée. Le registre indique PIT_VERIFIED pour cette capacité de source ; **cela ne signifie pas que des vecteurs vérifiés ont déjà été construits**. La prochaine étape devra utiliser les intervalles collectés avant toute transformation ou propagation.

### Taux, spread, WTI et prix S&P 500

Ils restent PIT_APPROXIMATED selon les conventions de la spec. Les fichiers de valeurs brutes ne certifient pas, à eux seuls, les heures réelles de publication. Le secours Yahoo est déclaré : aucun export S&P 500 Bloomberg n'a été fourni ou retrouvé. Aucun autre indice de portefeuille n'est utilisé comme proxy du S&P 500.

### Dollar DTWEXBGS — D003, bloquant avant un usage strict

La Fed publie le lundi les données quotidiennes de la semaine précédente, avec report au jour ouvré suivant lorsque le lundi est férié fédéral. J+1 pourrait donc anticiper la publication pour plusieurs observations de la semaine.

Le dernier point de cette collecte est le 09/10/2026, publié le 13/10/2026 ; la publication suivante est annoncée le 19/10/2026. La Fed mentionne également une interruption de H.10 de mai 2006 à janvier 2009.

**Aucune correction de délai décidée par l'agent.** La règle décrite dans la config reste celle de la spec, mais elle n'est pas appliquée : le registre marque pit_rule_requires_decision=True et pit_capability=publication_delay_requires_validation. Le point doit être validé dans DECISIONS.md avant l'étape PIT de l'échantillon R. H n'utilise pas le dollar.

Preuves : [publication H.10](https://www.federalreserve.gov/releases/h10/), [fiche DTWEXBGS](https://fred.stlouisfed.org/series/DTWEXBGS).

### GPR/EPU — D004, limite de source documentée

Les fichiers actuels n'offrent pas un historique complet de millésimes et dates de publication. L'éditeur EPU peut réviser les deux mois précédents. Le délai M+10 jours de la spec est une convention ; il ne prouve pas que la valeur téléchargée aujourd'hui était exactement celle disponible à une date passée.

Le statut est **CONTEMPORARY_INPUT_RETRO_METHOD**, jamais PIT_VERIFIED. Les archives commencent à la date de chaque téléchargement, sans prétendre recréer des archives antérieures. La future ablation stricte avec/sans GPR et EPU reste obligatoire. Ces limites sont inscrites dans DECISIONS.md sans changement de paramètre.

## 4. Tests et contrôles

| Contrôle | Résultat |
|---|---|
| Installation des dépendances et imports sous Python 3.14.0 | PASSE |
| pip check | PASSE |
| ruff check macro_engine | PASSE |
| ruff format --check macro_engine | PASSE |
| Tests existants quant-lab | 52 passes |
| Tests de collecte macro | 12 passes |
| Ensemble explicite tests + macro_engine/tests | **64 passes, 11,31 s** |
| Vraie collecte finale | **10/10 collected, sortie 0** |
| Empreintes des 14 sources et fichiers Parquet/ALFRED | Vérifiées |
| Identité SPEC.md avec le gel spec-v1.0 | Conservée |
| Diff du code cœur, des exigences racine et de la CI contre 1bda389 | Vide |

Les douze tests couvrent :

1. Interdiction d'écraser un fichier de cache ou de sortir de son répertoire.
2. Conservation des valeurs FRED manquantes, sans remplissage.
3. Conservation de deux versions ALFRED d'une observation et des bornes de validité.
4. Rejet des clés d'observations dupliquées.
5. Sélection de l'EPU presse, sans raccord pré-1985.
6. Reconnaissance de la note d'attribution EPU ; rejet des données malformées.
7. Refus de substituer GPRH/GPR_OLD à GPR.
8. Absence de clé API dans les métadonnées et erreurs.
9. Refus d'archiver une réponse qui répercuterait la clé.
10. Pagination FRED complète avec offsets.
11. Rejet d'une pagination tronquée.
12. Séparation des fichiers courants FRED, des métadonnées de millésimes et des observations ALFRED.

Les cinq défauts de formatage préexistants hors module restent hors périmètre. La CI n'est pas modifiée pour y ajouter le module ; les commandes de vérification macro sont donc explicites.

**Le test de troncature état/régimes/analogues et les autres tests de la section 12 ne sont pas déclarés passants : ces composants n'existent pas encore.** Le test de troncature sera écrit dès que l'état quotidien existera, conformément à la consigne.

## 5. Traçabilité, incidents de développement et reproduction

Commits de l'étape :

- **31bb653** : décisions validées, config et dépendances séparées Python 3.14.
- **de94172** : collecteur, cache, douze tests et limitations PIT documentées.
- Un commit documentaire supplémentaire porte le présent rapport après la collecte.

Un premier run de contrôle dans le cache 20261018T143305.600189Z a révélé une collision de noms entre observations FRED courantes et ALFRED, ainsi que la note de bas de feuille EPU. Ce run portait git_dirty=True et n'est pas le jeu de référence du rapport. Il est conservé intact, sans réécriture de son cache. Les correctifs sont couverts par des tests ; la collecte finale de référence a été entièrement retéléchargée depuis de94172 avec un dépôt propre.

Reproduire l'environnement et une nouvelle collecte :

~~~text
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r macro_engine/requirements.txt
./.venv/Scripts/python.exe -m pip check
# Définir FRED_API_KEY dans l'environnement sans enregistrer sa valeur.
./.venv/Scripts/python.exe -m macro_engine.collect
# Si un export S&P 500 Bloomberg est disponible :
./.venv/Scripts/python.exe -m macro_engine.collect --sp500-bloomberg chemin/export.csv
~~~

Le schéma documenté pour cet export préféré est date + PX_LAST, en CSV, XLSX ou Parquet. Un export illisible ou de schéma différent bloque cette source ; il n'est pas remplacé silencieusement par Yahoo. Les téléchargements futurs pourront contenir d'autres données : les comparaisons devront utiliser un cache figé identifié, pas des collectes à des dates différentes.

Les journaux d'installation, de tests et de collecte restent locaux, à côté de la copie de travail. Aucun cache, fichier Parquet, registre généré ou journal d'exécution n'est committé. Le rapport ne contient que les métadonnées agrégées de couverture, pas des séries brutes.

## 6. Arrêt demandé

**STOP ÉTAPE 02.** Pas de pit.py, transform.py, state.py, normalisation, analogues, graphiques ou comparaison de stratégies à cette étape.

À faire examiner par Claude : code de collecte, sécurité du cache et des secrets, exhaustivité des millésimes, portée exacte des statuts de source, et décision D003 sur le dollar. La règle proposée pour ce dernier reste à valider par l'utilisateur ; aucun contournement n'a été appliqué.

Main et la branche 80/20 ne sont pas modifiés. Aucun ordre, aucun tag live, aucune fusion et aucune réécriture d'historique.
