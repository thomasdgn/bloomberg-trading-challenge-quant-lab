# Décisions macro — validations et limites de collecte

SPEC.md reste inchangé. Les validations ci-dessous proviennent du retour explicite de l'utilisateur sur le rapport de l'étape 01, le 18 octobre 2026.

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

**Statut : BLOQUANT POUR L'USAGE STRICT DU DOLLAR, EN ATTENTE DE VALIDATION.**

Constat officiel au 18 octobre 2026 :

- La série est quotidienne, mais la Fed publie les observations de la semaine précédente le lundi à 16 h 15 heure de l'Est, ou le jour ouvré suivant si ce lundi est férié fédéral.
- Le dernier point disponible est le 09/10/2026, publié le 13/10/2026 ; la prochaine publication est annoncée le 19/10/2026.
- Une observation du lundi pourrait donc être utilisée avant publication si on appliquait simplement J+1.
- La page officielle indique aussi une interruption de publication H.10 de mai 2006 à janvier 2009 ; les dates de disponibilité historiques sur cette période ne doivent pas être inventées.

Sources : https://www.federalreserve.gov/releases/h10/ et https://fred.stlouisfed.org/series/DTWEXBGS.

La collecte brute reste possible. Le registre marque pit_rule_requires_decision=True et pit_capability=publication_delay_requires_validation. La règle figée J+1 dans la description de configuration n'est pas appliquée ou remplacée ; aucun vecteur strict n'est construit.

Proposition à faire valider avant l'étape PIT : exception explicite pour le dollar, fondée sur les dates de publication historiques H.10/ALFRED ou, lorsque la preuve manque, une convention conservatrice documentée. Le traitement de 2006-2009 doit être décidé séparément si les dates historiques ne peuvent pas être vérifiées.

Ce point concerne l'échantillon R. Le dollar n'est pas ajouté à H et aucun raccord avec une autre série de dollar n'est effectué.

## D004 — GPR et EPU : archives actuelles et dates non certifiées

**Statut : LIMITATION DOCUMENTÉE ; AUCUN CONTOURNEMENT APPLIQUÉ.**

Les fichiers officiels sont téléchargeables automatiquement. Ils ne contiennent ni millésimes historiques complets ni dates de publication réelles par observation.

- GPR : colonne GPR de la version de référence, uniquement depuis 1985 ; pas de substitution par GPRH ou GPR_OLD.
- EPU : feuille Main News Index, colonne News_Based_Policy_Uncert_Index, uniquement depuis 1985 ; pas d'utilisation de l'indice composite historique ou de raccord avec la méthodologie pré-1985.
- L'éditeur EPU documente de possibles révisions des deux mois précédents : https://www.policyuncertainty.com/us_monthly.html.
- Le délai M+10 jours est la convention de SPEC.md ; il ne certifie pas que la valeur téléchargée aujourd'hui était exactement celle publiée à cette date passée.

Le statut reste CONTEMPORARY_INPUT_RETRO_METHOD, jamais PIT_VERIFIED. Les téléchargements sont archivés avec leur date et leur empreinte. La future étape PIT doit conserver cette limitation ; l'ablation avec/sans GPR et EPU reste obligatoire en mode strict. Aucune série n'est requalifiée et aucune règle de disponibilité n'est implémentée à l'étape 02.

## Suivi des validations

| ID | Décision validée | Date | Validation utilisateur |
|---|---|---|---|
| D001 | Quatre semaines ; cible quant-lab lue directement pour IC | 2026-10-18 | Retour explicite sur RAPPORT_MACRO_ETAPE_01 |
| D002 | Dépendances macro séparées, figées ; pas de modification CI | 2026-10-18 | Retour explicite sur RAPPORT_MACRO_ETAPE_01 |
| D003 | Exception de disponibilité du dollar | — | En attente avant usage strict |
| D004 | Limites des fichiers actuels GPR/EPU | 2026-10-18 | Constat de collecte, pas une nouvelle validation |
