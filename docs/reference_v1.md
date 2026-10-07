# V1 : données, risque relatif et allocation de référence

La branche `feature/robust-optimization` fournit maintenant une chaîne exécutable
**exports → rendements hebdomadaires USD → covariance jointe titres/WLS → poids
à tracking error minimale**. Elle produit une référence de recherche sans alpha.
Les Excel, les exports sources et `src/covariance.py` sont conservés.

## Installation et démonstration

Depuis la racine du dépôt, avec Python 3.14 :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.run_reference --demo --output outputs/reference_demo_001
```

La démonstration utilise huit titres fictifs, 52 rendements hebdomadaires et un
benchmark synthétique. Elle teste la mécanique, pas la rentabilité d'une stratégie.
Le dossier de sortie contient `report.json` et `reference_weights.csv`. Une seconde
exécution doit choisir un autre dossier : aucun run existant n'est écrasé.

`status=reference_computed` signifie que la référence a été calculée et ses
contraintes contrôlées. **`ready_for_trading` reste toujours `false`** dans ce
chantier : frais, cash, quantités, ordres en attente et règles d'exécution ne sont
pas encore intégrés. Un run bloqué produit seulement un rapport, sans poids.

## Passage aux exports réels

Créer localement dans `outputs/` :

1. `candidates.csv`, une seule colonne `id`, avec une sélection explicite de
   tickers Bloomberg membres du WLS. L'ordre est conservé et toutes les jointures
   se font par identifiant. Les membres sans historique ou convention valide
   seront signalés comme exclus. Le nombre de titres doit permettre le plafond
   choisi ; avec 18 % par titre, il en faut au moins six.
2. `conventions.json`, sur le modèle de `configs/reference_conventions.example.json`.
   Faire confirmer les champs par le responsable Data/Terminal. Les valeurs
   inconnues du modèle sont intentionnelles : ne pas les remplacer par des
   hypothèses présentées comme vérifiées.
3. Si nécessaire, `fx.csv`, contenant `date` puis une colonne par devise utilisée,
   cotée en **USD par unité principale de devise**. Les observations doivent être
   datées, positives et cohérentes avec celles des prix. Aucun FX n'est reporté
   depuis une autre date.

Exemple de commande après confirmation des conventions :

```powershell
.\.venv\Scripts\python.exe -m scripts.run_reference `
  --input data/bloomberg/data `
  --candidates outputs/candidates.csv `
  --conventions outputs/conventions.json `
  --fx outputs/fx.csv `
  --as-of 2026-10-12 `
  --cutoff 2026-10-09 `
  --weeks 52 --min-observations 40 --max-age-days 4 `
  --max-weight 0.18 `
  --output outputs/reference_2026-10-12_001
```

Omettre `--fx` uniquement si tous les titres acceptés sont déjà en USD. Un export
allant seulement au 7 octobre ne peut pas certifier les clôtures du vendredi 9 :
les compléter avant cette commande. La date de décision est volontairement
conservative : le cutoff doit être un vendredi **antérieur au jour** de décision.

### Contrat des conventions

Chaque titre utilise ces champs :

| Champ | Sens |
|---|---|
| `verified` | `true` seulement après vérification des conventions de cet export |
| `evidence` | Référence non vide à la preuve de vérification, gardée localement si confidentielle |
| `available_at` | Date/heure ISO sans fuseau dans la même convention temporelle que `as_of`, au plus tard à la décision |
| `currency` | Devise principale, trois lettres majuscules ; aucune inférence à partir du ticker |
| `price_unit_multiplier` | Conversion du prix source en unité principale : 1 en dollars/livres, 0.01 en cents/pence |
| `adjustment` | `split_adjusted_price` : prix corrigé des splits, sans réinvestissement des dividendes |

Le benchmark exige `id="WLS Index"`, `currency="USD"`, `return_type="price"`,
avec les mêmes champs de vérification/provenance. Chaque devise FX exige
`quote="USD_per_unit"` et ses propres preuves. Le module convertit
`prix_USD = prix_source × multiplicateur × FX`; un titre USD utilise un FX de 1.

Un ajustement total return est refusé pour cette V1 avec WLS Price Return.
L'effet des dividendes sur le score TMSG reste à confirmer et devra être traité
dans le suivi de portefeuille. La V1 ne reconstitue ni les splits ni les FX absents.
Les éléments du manifest sont des déclarations traçables, pas une vérification
automatique des paramètres de téléchargement Bloomberg.

## Règles de préparation

- Dates journalières uniques, ordonnées, sans fuseau ; colonnes titres uniques.
  Les observations au-delà du cutoff sont ignorées avant le calcul des rendements.
- Les observations non manquantes doivent être finies et strictement positives.
- Chaque clôture hebdomadaire est la dernière observation de sa semaine W-FRI,
  seulement si son âge ne dépasse pas `max_age_days` jours calendaires. Ce seuil
  explicite ne remplace pas un calendrier de place : vérifier les jours fériés.
- Aucun remplissage des prix/FX et aucun rendement remplacé par zéro. Une clôture
  manquante invalide les rendements qui l'utilisent comme départ ou arrivée.
- Un titre dont la dernière clôture est manquante/périmée ou l'historique trop
  court est exclu avec un motif. Le rapport indique le poids **actuel** WLS couvert.
- Les dates restantes doivent être communes à tous les titres retenus et au WLS.
  Les dates retirées sont publiées. Si moins de `min_observations` restent, le run
  bloque et demande une sélection explicite ; il ne réduit pas discrètement l'univers.
- L'univers complet fourni doit avoir des poids sommant à 1. Ces poids servent
  au diagnostic de couverture et ne sont jamais renormalisés pour remplacer le WLS.

## Modèle de risque et optimiseur

`src/risk_relative.py` appelle `estimate_ledoit_wolf` du module existant sur les
rendements joints des titres **et de la série réelle du WLS**, sur les mêmes dates.
Il refuse toute suppression cachée de ligne ou de colonne par cet estimateur.
Le modèle est `C`, covariance hebdomadaire jointe, et `x=[w;-1]` :

```text
TE_week = sqrt(x.T C x)
minimiser TE_week²
sous sum(w)=1, 0 <= w <= cap
et bornes d'exposition explicites lorsqu'elles sont fournies.
```

Le facteur `F` satisfait `F.T @ F = C`. Une covariance matériellement non PSD ou
asymétrique est refusée ; seuls les petits écarts numériques négatifs sont tronqués.
Le Ledoit-Wolf joint peut augmenter la TE modélisée d'une réplication historique
exacte : son shrinkage est publié et la TE n'est pas confondue avec l'écart-type
empirique des rendements actifs.

`src/optimisation.py` utilise CVXPY/CLARABEL. Le statut doit être `optimal` ;
`optimal_inaccurate`, l'échec du solveur ou une allocation infaisable bloquent.
Une vérification indépendante contrôle somme, positivité, caps et expositions
à une tolérance de 1e-8. Aucun clipping/renormalisation ne masque ces résidus.
Les poids restent numériques, avant arrondis d'exécution.

Le plafond interne par défaut est 18 %. Le moteur accepte des caps individuels
par identifiant et des bornes d'exposition via l'API Python. Les coefficients et
bornes sectorielles/pays restent à fournir ; aucune neutralité n'est présumée.
La CLI fournit pour l'instant les caps et un éventuel plafond de TE hebdomadaire.
`--max-te-weekly` est une fraction : 0.01 signifie 1 % par semaine. Le minimum
faisable est calculé d'abord, puis comparé au plafond ; un plafond irréalisable
ne relâche aucune contrainte.

La TE annualisée publiée est `sqrt(52) × TE_week`, une approximation supposant
l'absence de dépendance temporelle, pas une prévision de performance. Le modèle
est centré ; il ne minimise pas le biais moyen ni ne promet de battre l'indice.
Les secteurs/pays, coûts et incertitude d'alpha viendront dans les étapes suivantes.

## Traçabilité et validation

Chaque run réel conserve les SHA-256 des prix, du benchmark, de l'univers, de la
liste de candidats, des conventions et des FX éventuels, ainsi que les paramètres
et la révision Git, l'état du checkout, les empreintes des modules et les versions
des bibliothèques de calcul. Pour les usages partagés, exécuter depuis un checkout propre
et conserver les fichiers de données correspondants. Les sorties sont ignorées
par Git et aucun fichier de données source n'est modifié.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
.\.venv\Scripts\python.exe -m pytest
```

Les tests couvrent la conversion FX/sous-unités, les trous et prix périmés,
l'absence d'anticipation, les calendriers incompatibles, les conventions inconnues,
la covariance jointe, une réplication exacte analytique, des caps/expositions
infaisables, le réordonnancement des identifiants, les statuts solveur et le refus
d'export après blocage. Ils ne constituent pas un backtest de performance.

Validation locale du 8 octobre 2026 : **59 tests passent**, dont les tests
d'import/covariance existants ; Ruff et `pip check` passent. La démonstration
complète produit une référence ; les exports réels avec le manifest non confirmé
produisent un rapport bloqué sans fichier de poids, comme attendu. Le workflow
GitHub vérifie également cette branche sous Windows et Linux.

## Suite immédiate

Faire vérifier les conventions réelles et livrer une liste de candidats avec
métadonnées de liquidité/pays/secteur. Puis comparer cette référence aux signaux,
ajouter l'incertitude d'alpha et construire les contrôles cash/tickets USD.
Le [message à envoyer à l'équipe](message_equipe_tmsg.md) prépare les confirmations
TMSG nécessaires. Le [plan de lancement](plan_lancement_lundi.md) reste la liste
des prérequis pour les premiers trades.
