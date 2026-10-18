# Décisions macro — en attente de validation

SPEC.md reste inchangé. Ce fichier distingue les propositions des décisions effectivement validées. À la date du 18 octobre 2026, aucun écart n'a été implémenté.

## D001 — Horizon de l'évaluation et cible de comparaison

**Statut : EN ATTENTE.**

Constat :

- SPEC.md section 7.3 donne h = 25 séances par défaut et demande de vérifier l'horizon dans quant-lab.
- Le chemin historique reste à cinq semaines.
- La nouvelle stratégie finale de main définit HORIZON_WEEKS = 4, TARGET_4W = future_excess_return_4w, dans src/strategies/final_four_week/constants.py.
- La spec ne doit pas être modifiée pour masquer ce changement.

Choix à faire valider :

1. Conserver 25 séances pour le MVP macro et sa référence historique cinq semaines.
2. Aligner les futurs calculs concernés sur la stratégie quatre semaines, avec une convention NYSE explicite pour traduire l'horizon.

Impact : éligibilité des analogues, horizon des évaluations conditionnelles et périodes non chevauchantes. Le paramètre sera centralisé dans config.py une fois le choix validé.

**Aucun choix effectué dans du code macro.**

## D002 — Fichier de dépendances propre au module

**Statut : EN ATTENTE.**

Constat :

- SPEC.md section 10 demande des versions figées et inclut notamment pandas-market-calendars et plotly.
- Ces deux dépendances ne sont pas dans les exigences actuelles du dépôt.
- La consigne utilisateur interdit la modification des fichiers existants de quant-lab hors .gitignore.

Proposition : créer macro_engine/requirements.txt pour les dépendances du module, avec des versions vérifiées et figées, sans modifier requirements.txt ni requirements-lock.txt à la racine.

**Aucun fichier de dépendances macro ajouté et aucune version sélectionnée à ce stade.**

## Suivi des validations

| ID | Décision validée | Date | Validation utilisateur |
|---|---|---|---|
| D001 | En attente | — | — |
| D002 | En attente | — | — |
