# Où ranger les données

On conserve les exports d'origine et on travaille sur des copies. Cela permet de
revenir à la source si un chiffre semble étrange.

| Dossier | Ce qu'on y met |
|---|---|
| `raw/` | Les exports Bloomberg tels qu'ils ont été récupérés |
| `interim/` | Les tables importées, encore en cours de vérification |
| `processed/` | Les tables validées pour les modèles et le backtest |

Tout le contenu de `data/` est ignoré par Git, sauf ce petit guide. Les fichiers
`WLS.xlsm` et `wls.xlsx` restent pour l'instant à la racine et sont eux aussi ignorés.

## Les informations à garder avec chaque export

Note la date d'extraction, la requête Bloomberg, les titres concernés, les périodes,
les devises et les unités. Pour les prix, précise les ajustements appliqués.
Pour une variable historique, indique quand elle était réellement disponible.
Si une information manque, écris « à confirmer » plutôt que de la deviner.

## Pour que tout le monde utilise la même version

Choisissons un dossier partagé et un nom clair pour chaque export. Gardons aussi
son empreinte de fichier, qui permet de vérifier que chacun utilise la même copie.
Les données de test inventées vont dans `tests/fixtures/`, en dehors de `data/`,
pour pouvoir être versionnées.

## Le premier import

Le script `src/import_wls.py` lit la feuille `WLSIndexData` de `wls.xlsx`.
Pour la copie auditée, il conserve 6 857 titres, dont 6 854 lignes numériques
complètes. Il signale trois volatilités manquantes et cinq rendements identiques
sur les trois horizons.

Dans `interim/wls_2026-10-02/`, on trouve :

- `snapshot.parquet` : les valeurs brutes et leur provenance.
- `anomalies.csv` : ce qu'il faut vérifier, avec les cellules Excel concernées.
- `report.json` : les comptes de lignes et les conventions encore inconnues.
- `data_dictionary.json` : les colonnes, les en-têtes Bloomberg et les périodes.

Ce dossier est local et ignoré par Git. La date de fin des indicateurs n'est pas
présentée comme la date effective du prix. Aucun rendement n'est converti en
pourcentage et aucune volatilité manquante n'est remplacée par zéro.
Les fichiers restent dans `interim/` tant que les conventions ne sont pas confirmées.
