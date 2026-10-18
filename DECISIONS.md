# Décisions macro — validations et limites de collecte

SPEC.md reste inchangé. Les validations ci-dessous proviennent des retours explicites de l'utilisateur sur les étapes 01 et 02, le 18 octobre 2026. Le présent complément est documentaire : les règles D003 à D007 ne sont pas implémentées avant le message explicite « GO ÉTAPE 03 ».

## D001 — Horizon de l'évaluation et cible de comparaison

**Statut : VALIDÉE par l'utilisateur le 18 octobre 2026.**

Constat :

- SPEC.md section 7.3 donne h = 25 séances par défaut et demande de vérifier l'horizon dans quant-lab.
- Le chemin historique reste à cinq semaines.
- La nouvelle stratégie finale de main définit HORIZON_WEEKS = 4, TARGET_4W = future_excess_return_4w, dans src/strategies/final_four_week/constants.py.
- La spec ne doit pas être modifiée pour masquer ce changement.

Décision appliquée dans macro_engine/config.py : **h = 4 semaines**, stratégie final_four_week. Ne pas convertir silencieusement ces semaines en 20 séances. Le commentaire de configuration rappelle que l'embargo de 365 jours calendaires rend la condition 7.3.3 redondante pour la sélection d'analogues à cet horizon.

**Règle validée pour la future phase IC : le module macro ne recalcule jamais le rendement futur.** Il lit directement la cible fournie par quant-lab : future_excess_return_4w pour final_four_week, ou future_excess_return_5w pour l'ancienne stratégie. Aucune cible ou évaluation IC n'est calculée à l'étape 02.

## D002 — Fichier de dépendances propre au module

**Statut : VALIDÉE par l'utilisateur le 18 octobre 2026.**

Constat :

- SPEC.md section 10 demande des versions figées et inclut notamment pandas-market-calendars et plotly.
- Ces deux dépendances ne sont pas dans les exigences actuelles du dépôt.
- La consigne utilisateur interdit la modification des fichiers existants de quant-lab hors .gitignore.

Décision appliquée : macro_engine/requirements.txt séparé, versions directes et transitives figées après installation réussie dans un environnement Python **3.14.0** propre. Aucun fichier d'exigences racine modifié. Aucune modification de CI dans le MVP.

Le module doit passer ruff check et ruff format. Les défauts de formatage préexistants hors module restent hors périmètre.

Le fichier GPR officiel est un classeur Excel 97-2003 .xls : xlrd==2.0.2 est ajouté pour le lire, sans changement de source ni substitution de série. yfinance est inclus pour le secours S&P 500 explicitement prévu par SPEC.md. L'installation et les imports de ces dépendances sont vérifiés sous Python 3.14.

## D003 — Dollar DTWEXBGS : conflit entre J+1 et publication hebdomadaire

**Statut : VALIDÉE SOUS CONDITION par l'utilisateur le 18 octobre 2026 ; condition vérifiée. Application logicielle différée.**

Constat officiel au 18 octobre 2026 :

- La série est quotidienne, mais la Fed publie les observations de la semaine précédente le lundi à 16 h 15 heure de l'Est, ou le jour ouvré suivant si ce lundi est férié fédéral.
- Le dernier point disponible est le 09/10/2026, publié le 13/10/2026 ; la prochaine publication est annoncée le 19/10/2026.
- Une observation du lundi pourrait donc être utilisée avant publication si on appliquait simplement J+1.
- La page officielle indique aussi une interruption de publication H.10 de mai 2006 à janvier 2009 ; les dates de disponibilité historiques sur cette période ne doivent pas être inventées.

Sources : https://www.federalreserve.gov/releases/h10/ et https://fred.stlouisfed.org/series/DTWEXBGS.

Vérification réelle de series/vintagedates pour DTWEXBGS, arrêtée au 18/10/2026 :

| Nombre de millésimes | Plus ancien | Plus récent |
|---:|---|---|
| 402 | 2019-02-04 | 2026-10-13 |

Règle validée pour la future étape PIT :

1. La disponibilité d'une observation est le realtime_start du premier millésime ALFRED qui la contient ; statut PIT_VERIFIED.
2. Toute observation dont la date de référence précède le 04/02/2019 est RETROSPECTIVE, utilisable uniquement en mode descriptif. Sa présence dans un millésime ultérieur n'autorise pas son usage strict.
3. Le premier millésime étant postérieur à 2010, **R est descriptif uniquement dans le MVP**. Cette restriction reste applicable même si une fenêtre stricte plus récente serait techniquement envisageable.
4. Aucun raccord avec une autre série de dollar, aucune disponibilité reconstruite par simple J+1.

Borne documentaire de faisabilité d'un éventuel R strict, hors livraison MVP :

- Première observation non rétrospective : 04/02/2019 ; premier millésime la contenant : 11/02/2019.
- Pour la variation dollar sur 252 séances NYSE, première paire admissible : 04/02/2019 → 04/02/2020.
- Premier millésime contenant les deux extrémités : 10/02/2020 ; premier état R strict théoriquement possible à cette date.
- La 1 260e séance NYSE à partir du 10/02/2020 inclus est le **12/02/2025** : première borne possible pour une distance, sous hypothèse de complétude de toutes les autres variables.

Ce n'est pas une date de production certifiée : aucun état, transformation, normalisation ou distance n'a été calculé dans le module. Des données manquantes pourraient reporter cette date. L'analyse documentaire utilise le calendrier NYSE de pandas-market-calendars 5.5.0 et les intervalles ALFRED interrogés hors du cache de référence.

Le registre immuable de l'étape 02 conserve ses anciens indicateurs de décision en attente ; il n'est pas réécrit pour simuler une validation antérieure. Les preuves dollar supplémentaires restent hors du cache épinglé et n'alimenteront pas les étapes suivantes. Le cache de référence ne contient pas les intervalles ALFRED du dollar, ce qui interdit de présenter un R strict exécutable à partir de ce seul cache.

## D004 — GPR et EPU : archives actuelles et dates non certifiées

**Statut : VALIDÉE TELLE QUE DOCUMENTÉE par l'utilisateur le 18 octobre 2026.**

Les fichiers officiels sont téléchargeables automatiquement. Ils ne contiennent ni millésimes historiques complets ni dates de publication réelles par observation.

- GPR : colonne GPR de la version de référence, uniquement depuis 1985 ; pas de substitution par GPRH ou GPR_OLD.
- EPU : feuille Main News Index, colonne News_Based_Policy_Uncert_Index, uniquement depuis 1985 ; pas d'utilisation de l'indice composite historique ou de raccord avec la méthodologie pré-1985.
- L'éditeur EPU documente de possibles révisions des deux mois précédents : https://www.policyuncertainty.com/us_monthly.html.
- Le délai M+10 jours est la convention de SPEC.md ; il ne certifie pas que la valeur téléchargée aujourd'hui était exactement celle publiée à cette date passée.

Le statut reste CONTEMPORARY_INPUT_RETRO_METHOD, jamais PIT_VERIFIED. Les téléchargements sont archivés avec leur date et leur empreinte. La future étape PIT doit conserver cette limitation ; l'ablation avec/sans GPR et EPU reste obligatoire en mode strict. Aucune série n'est requalifiée et aucune règle de disponibilité n'est implémentée dans ce complément.

## D005 — S&P 500 : Yahoo ^GSPC retenu pour le MVP

**Statut : VALIDÉE par l'utilisateur le 18 octobre 2026 ; application logicielle différée.**

Yahoo Finance ^GSPC est la source retenue pour la volatilité réalisée du MVP : clôtures de l'indice, sans réinvestissement de dividendes. Ce n'est plus un secours provisoire. La variable macro reste l'écart-type annualisé des log-rendements sur vingt séances, conformément à SPEC.md ; aucune transformation n'est encore effectuée.

Le cache de référence contient déjà les clôtures ^GSPC requises, téléchargées par yfinance avec auto_adjust=False. Ses métadonnées historiques emploient le mot « fallback » parce que c'était la politique au moment de la collecte ; elles restent intactes. La décision actuelle remplace cette politique pour l'usage futur sans modifier la source téléchargée ni la provenance passée.

## D006 — Cache de référence épinglé

**Statut : VALIDÉE par l'utilisateur le 18 octobre 2026.**

Référence unique approuvée :

    macro_engine/cache/20261018T143956.868547Z/

Toutes les étapes suivantes devront lire uniquement ce cache, vérifier ses empreintes et ne pas sélectionner automatiquement le cache le plus récent. Toute nouvelle collecte de référence exige une décision explicite de l'utilisateur.

Le registre source_registry.csv et le manifeste run_manifest.json restent inchangés. Les requêtes dollar de ce complément sont des preuves documentaires hors cache ; elles ne constituent pas un nouveau jeu de référence.

Clarification explicite de l'utilisateur le 18 octobre 2026 : **documentation uniquement ; constante à l'étape 03**. L'ajout de la constante et l'application du verrou de lecture dans config.py seront effectués uniquement après le message « GO ÉTAPE 03 », avant tout traitement de cette étape. Aucun comportement de collecte ou de lecture n'est changé dans le présent complément.

## D007 — Troncature sans historique suffisant

**Statut : VALIDÉE par l'utilisateur le 18 octobre 2026 ; test à écrire lors de l'étape concernée.**

Lorsqu'une date n'a pas l'historique minimal requis, le test compare entre données complètes et données coupées à t :

1. L'identité de l'état quotidien.
2. L'identité des étiquettes.
3. L'identité de l'absence d'analogues dans les deux exécutions.

Une absence attendue d'analogues n'est ni une erreur du test ni une autorisation d'abaisser le minimum de 1 260 séances. Cela s'applique notamment au cas 1990-08-15 s'il ne dispose pas d'un historique complet suffisant. Aucun état, étiquette ou analogue de cette date n'est calculé dans ce complément documentaire.

## Suivi des validations

| ID | Décision validée | Date | Validation utilisateur |
|---|---|---|---|
| D001 | Quatre semaines ; cible quant-lab lue directement pour IC | 2026-10-18 | Retour explicite sur RAPPORT_MACRO_ETAPE_01 |
| D002 | Dépendances macro séparées, figées ; pas de modification CI | 2026-10-18 | Retour explicite sur RAPPORT_MACRO_ETAPE_01 |
| D003 | Premiers millésimes ALFRED ; données antérieures rétrospectives ; R descriptif uniquement dans le MVP | 2026-10-18 | Retour explicite sur l'étape 02 ; premier millésime 2019 confirmé |
| D004 | GPR/EPU acceptés avec les limitations documentées | 2026-10-18 | Retour explicite sur l'étape 02 |
| D005 | Source S&P 500 Yahoo ^GSPC retenue pour le MVP | 2026-10-18 | Retour explicite sur l'étape 02 |
| D006 | Cache 20261018T143956.868547Z épinglé ; nouvelle référence sur décision explicite | 2026-10-18 | Retour explicite sur l'étape 02 |
| D007 | Troncature : états/étiquettes identiques et même absence d'analogues si historique insuffisant | 2026-10-18 | Retour explicite sur l'étape 02 |

## Arrêt de périmètre

Ce complément n'autorise aucune implémentation de l'étape 03. Le message **GO ÉTAPE 03** reste obligatoire avant de la commencer.

## D008 — Historique des analogues à quatre semaines, ajout hors SPEC

**Statut : VALIDÉE explicitement par l'utilisateur lors du GO ÉTAPE 05 et de sa réponse sur les vendredis fériés.**

Ajout indépendant, sans modification de SPEC.md : calculer H strict avec et sans GPR/EPU pour une grille de quatre semaines ancrée au 06/11/2020 et bornée au 16/10/2026. Un vendredi théorique fermé au NYSE est ramené à la dernière séance NYSE précédente. Les deux dates sont conservées dans le fichier long unique. La borne finale n'ajoute pas de date hors grille : dernier vendredi théorique le 02/10/2026, 78 dates théoriques au total.

Chaque date est reconstruite après troncature indépendante des observations et des publications à la séance de requête ; aucune performance, cible future ou décision d'ordres n'est calculée. Les cinq épisodes constituent un maximum selon les règles figées : les épisodes manquants ne sont pas inventés et les états de requête incomplets sont signalés. La stabilité reprend les neuf variantes fixées, sans réglage supplémentaire. Le script est séparé du point d'entrée MVP.
