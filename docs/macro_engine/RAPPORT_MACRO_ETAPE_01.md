# Rapport macro — étape 01 : préparation et gel de la spécification

Date : **18 octobre 2026**, Europe/Paris.

Ce rapport décrit une préparation de branche. Il ne constitue ni une validation de la stratégie actuelle, ni une livraison du moteur macro, ni un résultat de backtest.

## 1. Résultat de l'étape

La branche **feature/macro-engine** part exactement du main GitHub vérifié :

- Base : **1bda3897678168b1a980d44c3cddde892f417158**.
- Dernier changement de la base : « Merge final four-week strategy into main », 16 octobre 2026 à 23:45:44 +02:00.
- Commit de gel : **9c9204ac2e18aa485bef64f2e8500961955a0224**.
- Message : **Spec macro engine v1.0 figée**.
- Tag annoté : **spec-v1.0**, sur ce commit de gel.
- Date réelle du commit et du tag : **18 octobre 2026**. Ils ne sont pas antidatés au 16 octobre, date portée dans la spécification.

Le travail se déroule dans une copie de travail Git distincte. La copie habituelle du dépôt et ses fichiers de recherche non suivis sont préservés. Aucun commit ni déplacement de la référence main n'est effectué.

Cette étape est suivie d'un arrêt pour revue humaine et retour de Claude, conformément à la demande de progression par étapes. Aucune PR de livraison n'est ouverte à ce stade.

## 2. Fichiers du commit de gel

### SPEC.md

Copie exacte, octet pour octet, du fichier fourni :

    C:/Users/degar/Desktop/Code/Bloomberg Challenge/Analyse Macro/SPEC.md

Empreinte SHA-256 du fichier source, de la copie et du contenu Git vérifié :

    6b3e47b7d1119c2edb4e07dd6b79d19e371e889aac8a3781a15e1cb5fb44fce5

Taille : **21 902 octets**. Le contenu n'a été ni réécrit, ni reformulé. L'identité du blob indexé avec les octets du fichier a été vérifiée avant le commit, en désactivant la conversion automatique de fins de ligne pour cette indexation.

SPEC.md a été lu en entier. Il ne devra plus être modifié sur cette branche. Le tag protège l'identité de la version enregistrée ; il ne prouve pas que les choix historiques de variables ont été faits avant de connaître l'histoire.

### .gitignore

Ajout des exclusions demandées qui manquaient :

    macro_engine/cache/
    *.parquet
    macro_*.csv
    macro_diagnostics.html
    run_manifest.json

L'exclusion .env existait déjà. Les six cas demandés ont été vérifiés avec git check-ignore.

Le diff final du commit de gel est limité à **deux fichiers**, 340 lignes ajoutées : SPEC.md et .gitignore. Aucun code de quant-lab n'est modifié.

### Documentation ajoutée après le tag

- RAPPORT_MACRO_ETAPE_01.md : présent rapport de transmission.
- DECISIONS.md : points en attente de validation avant les choix concernés.

Le tag reste sur le commit de gel, antérieur à ce complément documentaire.

## 3. Ce qui a changé sur GitHub depuis l'audit initial

L'ancienne base auditée était **440eeff**. Le main GitHub est maintenant **1bda389**.

Nouveaux commits observés :

| Commit | Date Paris | Objet |
|---|---|---|
| 13644cc | 14/10/2026 23:28:50 | Pipeline et allocation 80/20, exports et métadonnées FX |
| 72687f7 | 16/10/2026 23:44:01 | Stratégie finale à quatre semaines et profils de risque |
| 1bda389 | 16/10/2026 23:45:44 | Fusion de cette stratégie dans main |

Le main courant comprend désormais notamment :

- src/refresh_feature_market_data.py, absent lors de l'audit initial ;
- src/weekly_data_update.py et un modèle Excel de mise à jour ;
- src/strategies/final_four_week/ ;
- config/final_strategy_profiles.json ;
- une génération d'export expliqué et un manifeste d'exécution ;
- des changements des historiques de prix et de volumes Bloomberg.

**Conséquence : les métriques de l'audit sur 440eeff ne sont pas les métriques de ce nouveau main.** Les données et le code ont changé ; elles ne seront pas réutilisées comme comparaison chiffrée avec le moteur macro.

La branche distante codex/strategie-80-20 n'a pas été modifiée. Sa présence dans l'ascendance du main provient du travail déjà intégré par le collaborateur.

## 4. Vérifications réalisées

La copie isolée correspond à la base 1bda389. Les dépendances sont identiques à celles de l'environnement Python 3.14.0 déjà installé pour l'audit 80/20 ; les fichiers requirements.txt et requirements-lock.txt n'ont pas changé entre cette version et le main courant.

| Contrôle | Résultat | Portée |
|---|---|---|
| pip check | PASSE | Aucune dépendance cassée |
| ruff check src tests | PASSE | Lint existant |
| pytest --basetemp dans le dossier de vérification | **52 tests passent en 21,05 s** | Tests existants de main |
| ruff format --check src tests | **ÉCHEC : 5 fichiers** | Défauts de formatage préexistants |
| Identité source/copie de SPEC.md | PASSE | Même SHA-256 |
| Identité fichier/blob de SPEC.md | PASSE | Aucune conversion lors de l'indexation |
| Exclusions gitignore demandées | PASSE | Six cas vérifiés |
| Diff et liste des fichiers du commit de gel | PASSE | SPEC.md et .gitignore seulement |
| CI distante du commit de base | **NON CONFIRMÉE** | Aucun run/statut renvoyé par le connecteur |

Fichiers concernés par l'échec de formatage :

1. src/compare_backtest_horizons.py
2. src/export_clean_allocations.py
3. src/opportunistic_model.py
4. src/refresh_feature_market_data.py
5. src/weekly_data_update.py

Ces fichiers n'ont pas été corrigés dans la branche macro. L'utilisateur a explicitement autorisé la préparation et le push de la branche après présentation de ces défauts préexistants.

Le pipeline complet courant n'a pas été réexécuté pendant cette étape de gel. Aucun nouveau backtest de performance, appel FRED ou téléchargement de données macro n'est réalisé. Les tests de la section 12 de SPEC.md n'existent pas encore : il serait incorrect de les déclarer passants.

Preuves locales :

    ../macro_main_tests_2026-10-18.log
    ../macro_main_lint_2026-10-18.log
    ../macro_main_format_2026-10-18.log

Ces journaux sont locaux, hors du commit. Les commandes ci-dessus permettent de reproduire les contrôles.

## 5. Limites quantitatives encore présentes dans la base

L'ajout de la stratégie quatre semaines ne constitue pas l'assainissement point-in-time demandé précédemment. L'inspection du chemin de backtest commun montre toujours :

1. **Univers conditionné à la cible future.** prepare_data, dans src/backtest_execution_v2.py, supprime les lignes avec cible manquante avant de former les ensembles de test.
2. **Absence de FX historique dans le calcul du PnL commun.** load_market_history, dans src/backtest_portfolio_v1.py, utilise directement les niveaux de prix ; un taux FX pour calculer la quantité des ordres n'est pas une conversion historique des rendements.
3. **Entrée à la date du signal possible.** simulate_stop_loss peut sélectionner la clôture du jour du signal alors que les variables incluent cette clôture.
4. **PnL non conditionné à l'exécution effective des limites.** Les limites sont simulées et comptées mais les rendements de tous les poids cibles sont utilisés, même en absence de remplissage.

Le nouveau backtest quatre semaines réutilise run_backtest de src/backtest_execution_v2.py ; il ne résout pas ces quatre défauts.

Le module opportuniste comporte toujours les risques temporels déjà décrits dans AUDIT_BRANCHES.md : prix non tronqués à une date historique fournie, FX les plus récents et objectifs analystes sans archive point-in-time. Ces risques ne sont pas corrigés ici.

La branche macro ne devra pas transformer ces résultats exploratoires en preuve de performance financière. L'assainissement du cœur reste un travail séparé, avec validation des données nécessaires, tests et ablations.

## 6. Points à trancher avant l'implémentation concernée

### Horizon de l'évaluation

SPEC.md section 7.3 mentionne 25 séances, correspondant au chemin historique cinq semaines, et demande une vérification dans quant-lab. La stratégie finale actuelle définit HORIZON_WEEKS = 4 et TARGET_4W = future_excess_return_4w.

La date de signal documentée est le 16 octobre et l'échéance le 13 novembre 2026. Quatre semaines ne doivent pas être converties silencieusement en 20 séances sans tenir compte du calendrier NYSE.

La décision est inscrite dans DECISIONS.md. **Aucun horizon n'a été choisi dans du code macro.**

### Dépendances du module

La spec exige notamment pandas-market-calendars et plotly, absents des exigences actuelles de quant-lab. L'utilisateur interdit de modifier les fichiers existants du dépôt sauf .gitignore.

Proposition en attente : fichier d'exigences propre au module, macro_engine/requirements.txt, avec versions vérifiées et figées, sans modification des exigences racine. Aucune dépendance macro n'a encore été ajoutée ou installée.

## 7. Périmètre macro et comparaison de stratégies

Le MVP spécifié répond à la recherche d'analogues et prépare l'étude des performances selon les régimes. Il interdit de modifier l'Elastic Net, l'optimiseur ou le portefeuille.

**Par conséquent, ajouter seulement ce MVP ne crée pas une nouvelle stratégie de trading.** À ordres identiques, main et main + analyse macro auront les mêmes rendements. Il ne faut pas présenter un graphique différent comme un effet macro sans règle de portefeuille définie et validée à l'avance.

L'utilisateur souhaite ensuite comparer les modèles avec des courbes destinées aux coéquipiers. Pour cette étape future, le protocole proposé est :

1. Identifier les variantes exactes et leurs SHA ; distinguer modèles prédictifs, construction du portefeuille et analyse macro descriptive.
2. Figer des entrées communes : prix, FX historiques, univers point-in-time, benchmark, périodes, horizon, coûts et hypothèses d'exécution ; conserver les empreintes.
3. Réentraîner et relancer les variantes sur ces entrées ; ne jamais comparer des fichiers sauvegardés issus de périodes ou données différentes.
4. Rapporter IC, rendement actif net vs WLS, tracking error, ratio d'information, drawdown et turnover ; dispersion entre calendriers et coûts inclus.
5. Produire un rapport visuel : richesses nettes avec WLS, richesse relative, drawdowns, rendements par période et dispersion des métriques. Fournir des exports partageables et, si utile, un rapport HTML.
6. Respecter le test de troncature et l'ensemble de la section 12 pour le moteur macro ; tenir les résultats historiques exploratoires séparés du test futur préenregistré.
7. Si une règle macro modifie ultérieurement les ordres, la soumettre à validation, puis à au moins un rééquilibrage en **mode fantôme**, sans transmission d'ordres, avec tableau production/nouvelle version.

Ce protocole est proposé pour revue ; aucune règle d'allocation macro, aucun budget de risque et aucun seuil de sélection n'ont été choisis ou optimisés.

## 8. État de la production et garde-fous

- L'achat Ford du 16 octobre 2026 a été déclaré manuel : 10 000 USD au prix annoncé de 12,30 USD. Il ne permet d'attribuer aucun commit de production.
- Aucun tag live n'est créé. spec-v1.0 est un gel de document, pas un tag de stratégie utilisée en réel.
- Aucun ordre n'est envoyé et aucune connexion de courtage n'est utilisée.
- Aucun secret, export Bloomberg ou donnée brute n'est ajouté aux commits de cette étape.
- Les données brutes déjà présentes dans l'ascendance Git ne sont ni effacées ni réécrites.
- Aucun force push, suppression de branche ou changement d'historique.
- Aucune fusion ou modification directe de main.
- Le code du module sera indépendant ; FRED_API_KEY sera lu dans l'environnement au moment de la collecte, jamais enregistré.

## 9. Prochaine étape proposée à la revue

Examiner ce rapport, SPEC.md et DECISIONS.md ; faire valider les décisions concernées par l'utilisateur. Après ce retour, l'implémentation pourra commencer par config.py et collect.py, avec des petits commits et un rapport à chaque étape. Le test de troncature sera écrit dès l'existence de l'état quotidien.

L'utilisateur transmet lui-même ce rapport à Claude. Aucune instruction n'est envoyée à un autre chat ou à un service de messagerie.

**ARRÊT À LA FIN DE L'ÉTAPE 01.** Pas d'implémentation du moteur ou de comparaison finale avant le retour demandé.
