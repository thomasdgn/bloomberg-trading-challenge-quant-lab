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

## Suivi des validations

| ID | Décision validée | Date | Validation utilisateur |
|---|---|---|---|
| D001 | Quatre semaines ; cible quant-lab lue directement pour IC | 2026-10-18 | Retour explicite sur RAPPORT_MACRO_ETAPE_01 |
| D002 | Dépendances macro séparées, figées ; pas de modification CI | 2026-10-18 | Retour explicite sur RAPPORT_MACRO_ETAPE_01 |
