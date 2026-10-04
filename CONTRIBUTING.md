# Travailler ensemble sur le dépôt

On est cinq sur le même projet. Pour avancer sans se gêner, chacun prend une tâche
précise et fait relire son travail avant de le fusionner.

## Une branche pour chaque tâche

Actualise ta branche principale avec `git pull --ff-only`, puis crée ta branche.
Choisis un nom qui dit ce que tu fais, par exemple `data/import-wls` ou
`backtest/controle-prix`.

Quand ton travail est prêt, ouvre une pull request : explique ce que tu as changé
et comment tu l'as vérifié. Un autre membre la relit avant la fusion. Si tu changes
le format d'un fichier utilisé par les autres, préviens-les avant de coder.

La relecture obligatoire et la protection de la branche principale doivent encore
être activées dans les paramètres GitHub.

## Ce qu'on garde dans Git

Le code, les notebooks utiles, la documentation et les petits jeux de données
inventés pour les tests. Mets ces jeux de test dans `tests/fixtures/`.

Les exports Bloomberg restent locaux. Les deux fichiers de départ restent pour
l'instant à la racine ; les prochains iront dans `data/raw/`. Les résultats générés
vont dans `outputs/`. Ces données et résultats sont ignorés par Git.

Il nous reste à choisir un dossier partagé pour que chacun récupère les mêmes
exports. Le `.gitignore` évite de les committer, mais ne les partage pas.

## Avant de committer

1. Regarde `git status` et `git diff`.
2. Ajoute seulement les fichiers de ta tâche avec `git add chemin/du/fichier`.
3. Relis `git diff --cached` et lance les contrôles utiles.

Garde les clés et mots de passe dans un `.env` local. Si besoin, un `.env.example`
peut montrer les variables à remplir, avec des valeurs fictives.

## Préparer Python

On utilise **Python 3.14** pour ce premier import. Les bibliothèques et leurs
dépendances sont figées dans `requirements-lock.txt` ; `requirements.txt` les installe.
Sous Windows, depuis le dossier du dépôt :

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Pas besoin d'activer l'environnement pour ces commandes. Sur macOS ou Linux,
crée-le avec `python3.14 -m venv .venv` et remplace le chemin Python par
`.venv/bin/python`. Le dossier `.venv` reste local et est ignoré par Git.

## Lancer le premier import

Avec ta copie locale de l'export :

```powershell
.\.venv\Scripts\python.exe src/import_wls.py --input wls.xlsx --output-dir data/interim/wls_2026-10-02
```

Si ton fichier est dans `data/raw/`, utilise `--input data/raw/wls.xlsx`.
Le dossier de sortie doit être nouveau : l'import ne remplace pas les résultats
d'une exécution précédente. Choisis un autre nom pour le relancer.

Il produit `snapshot.parquet`, `anomalies.csv`, `report.json` et `data_dictionary.json`.
Les valeurs restent brutes. Les trois volatilités manquantes deviennent des valeurs
nulles avec un motif ; aucun titre n'est supprimé. Les unités restent à confirmer
avec Data avant de parler de données validées pour un backtest.

## Vérifier avant de demander une relecture

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m ruff format --check src tests
```

Les tests créent de petits classeurs fictifs. L'équipe peut les lancer sans Terminal
Bloomberg ni export privé. GitHub Actions lance les mêmes contrôles sous Windows
et Linux ; les résultats distants restent à vérifier après publication de la branche.

## Partager le nettoyage actuel

Le travail est regroupé sur `codex/python-import-wls` pour relecture avant toute
fusion dans `main`. Les Excel sont retirés du suivi, mais leurs copies locales
restent intactes. Avant que les autres récupèrent la branche, demande-leur de
conserver une copie hors du dépôt. Les anciennes versions restent dans l'historique.
