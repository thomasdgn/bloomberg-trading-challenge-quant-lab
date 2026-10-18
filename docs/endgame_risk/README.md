# Outil de pilotage de fin de challenge

Branche `tools/endgame-risk`, créée depuis main `1bda389`. Outil autonome dans
`tools/endgame_risk/`, cœur en lecture seule. Aucun modèle de rendement, courtier,
ordre, modification de portefeuille réel ou lien avec la recherche macro.

## État de cette livraison

L'outil est préparé pour une analyse complète. **Les calculs réels restent bloqués**
tant que les positions exécutées, le cash rapproché et les données nécessaires ne
sont pas disponibles. Un montant prévu pour un ordre en attente n'est ni une
quantité exécutée ni une valorisation actuelle. Aucun portefeuille projeté n'est
présenté comme le portefeuille réel.

Le dépôt ne suffit actuellement pas : les historiques ne couvrent que 84,170392 %
du poids WLS, les FX ne contiennent qu'une date, les pays et unités de cotation
manquent et de nombreuses devises sont absentes. Les métadonnées et la composition
doivent être datées et vérifiées. Les dates de résultats Bloomberg ne sont pas
exploitables ; le champ `latest_announcement_dt()` a échoué à l'extraction.

## Exécution

Utiliser les dépendances existantes de quant-lab et son fichier de versions figées :
pandas, NumPy, scikit-learn, SciPy. Aucune dépendance ni CI existante modifiée.

```powershell
# Audit des données présentes : code retour 2 attendu lorsque bloqué.
.venv/Scripts/python.exe -m tools.endgame_risk.run --output-dir outputs/endgame_risk/audit_01

# Quand les entrées privées sont complètes :
.venv/Scripts/python.exe -m tools.endgame_risk.run --portfolio outputs/endgame_risk/inputs/portfolio.json --market-config outputs/endgame_risk/inputs/market.json --output-dir outputs/endgame_risk/analyse_01

# Règlement structuré facultatif, aucun réglage implicite de ses contraintes :
.venv/Scripts/python.exe -m tools.endgame_risk.run --portfolio outputs/endgame_risk/inputs/portfolio.json --market-config outputs/endgame_risk/inputs/market.json --rules outputs/endgame_risk/inputs/rules.json --output-dir outputs/endgame_risk/analyse_02

# Tests de cet outil exclusivement ; aucune recherche macro relancée.
.venv/Scripts/python.exe -m pytest tools/endgame_risk/tests -q
.venv/Scripts/python.exe -m ruff check tools/endgame_risk
.venv/Scripts/python.exe -m ruff format --check tools/endgame_risk
```

Les entrées et sorties privées vont dans `outputs/`, déjà ignoré par Git. Aucune
donnée de positions, clé, donnée brute ou export Bloomberg ne doit être ajouté à
un commit. Un répertoire de sortie existant est refusé. Aucun téléchargement,
rafraîchissement ou écrasement d'export n'est effectué.

## Portefeuille — JSON ou CSV associé

Exemple **fictif**, sans données du portefeuille réel :

```json
{
  "as_of_date": "2026-10-18",
  "status": "executed",
  "orders_pending": [],
  "positions": [
    {"id": "SYNTHETIC_A Equity", "quantity": 10, "currency": "USD"},
    {"id": "SYNTHETIC_B Equity", "quantity": 20, "currency": "EUR"}
  ],
  "cash": [{"currency": "USD", "amount": 1000}]
}
```

Alternative : remplacer `positions` par `"positions_file": "positions.csv"`.
Ce CSV contient `id,quantity,currency`, ou `id,market_value,currency,valuation_date`,
ou `id,weight`. Les identifiants Bloomberg complets sont requis pour les données
réelles. Les chemins relatifs sont résolus depuis le JSON qui les référence.

Les poids sont des **fractions de NAV**, cash compris, dont la somme est 1. En mode
poids, chaque ligne de positions et de cash déclare `weight` ; ne pas mélanger
montants, quantités et poids. Une valeur de marché est dans la devise déclarée,
avec `valuation_date` égale à `as_of_date`. Une quantité est valorisée au dernier
prix connu et au dernier FX connu au plus tard à la date du portefeuille. Les dates
de prix et de FX sont conservées séparément. La NAV est valorisée, jamais déduite
de montants investis historiques ou de budgets d'ordres.

Tout `orders_pending` non vide, statut autre que `executed`, quantité inconnue,
cash manquant du rapprochement ou incohérence de données bloque le calcul. La
présence d'un solde cash explicite, éventuellement nul, est requise pour confirmer
le rapprochement. Ne pas changer simplement le statut avant l'exécution réelle.

## Configuration de marché

```json
{
  "conventions_verified": true,
  "convention_source": "Référence du contrôle des conventions et unités",
  "available_at": "2026-10-16",
  "return_basis": "split_adjusted_price",
  "prices": "prices.csv.gz",
  "fx": "fx.csv",
  "metadata": "metadata.csv",
  "benchmark_weights": "wls_weights.csv",
  "benchmark_snapshot_date": "2026-10-16",
  "lookback_weeks": 52,
  "min_weeks": 40,
  "max_valuation_age_days": 7,
  "max_benchmark_age_days": 7
}
```

Ne pas déclarer `conventions_verified: true` sans vérification réelle. La source
de convention doit confirmer les devises, unités, ajustements et le périmètre des
rendements. Tous les titres utilisent la même base : prix ajustés des splits ou
indices total return, jamais un mélange. Ce sont des conventions de l'outil,
sans modification de la covariance ni des modèles quant-lab.

| Source | Schéma et exigences |
| --- | --- |
| `prices` | CSV large `date,<identifiants>` ; prix quotidiens positifs, dates uniques |
| `fx` | `date,currency,usd_rate` ; USD par unité monétaire majeure, historique quotidien |
| `metadata` | `id,currency,sector,country,price_unit_multiplier` ; aucune valeur manquante sur les lignes nécessaires |
| `benchmark_weights` | `id,index_weight` ; composition WLS complète, fractions positives, somme 1 |
| `earnings` facultatif | `id,event_date,available_at,source,status` ; dates connues, pas des prévisions inventées |

Les devises sont des codes majuscules à trois lettres. Les prix en pence, par
exemple, exigent `currency=GBP` et `price_unit_multiplier=0.01`. Le pays est la
classification explicitement fournie ; il n'est jamais déduit de la place de
cotation. Les catégories secteur/pays/devise décrivent les lignes, pas une
décomposition des revenus économiques de l'entreprise.

## Calculs et limites

1. Valorisation et poids USD, puis actifs `a = w_portefeuille − w_WLS`, cash inclus.
   La composition WLS actuelle sert à mesurer les expositions actuelles ; aucun
   backtest historique n'est créé. Tous ses sous-poids non détenus sont conservés.
2. Conversion des historiques en USD avec FX **de la date exacte du prix**.
   Aucun FX spot constant sur le passé, remplissage avant/arrière, proxy WLS,
   renormalisation du sous-univers disponible ou suppression implicite de ligne.
3. Fenêtre de 52 semaines, au moins 40 semaines complètes partagées, séances
   hebdomadaires terminées avant le jour de valorisation. Un point de semaine
   ne peut dater de plus de quatre jours calendaires avant son vendredi.
   Les tolérances de fraîcheur de valorisation/composition sont explicites.
4. Appel inchangé à `src.covariance.estimate_ledoit_wolf`. Annualisation `Σ_a = 52Σ` ;
   `TE = sqrt(a'Σ_a a)`. USD cash a un rendement nul et n'entre pas dans le
   shrinkage ; une ligne de covariance nulle est ajoutée après estimation. Le cash
   non USD conserve son risque FX, sans intérêt local. Aucun rendement de cash
   rémunéré n'est supposé. La matrice complète WLS peut demander beaucoup de mémoire.
5. Contribution marginale `m = Σ_a a / TE`, totale `a_i m_i`, fraction de TE
   `a_i m_i / TE`. Les contributions signées se somment à TE, par ligne et par
   chaque dimension de regroupement. À TE nulle, contributions nulles par convention.
6. Leviers homogènes `w' = w_WLS + k a`, pour k = 0,5 ; 0,75 ; 1,5. La TE théorique
   devient `k TE` à covariance constante. Le k = 1,5 peut créer des sous-poids
   correspondant à des ventes à découvert ; faisabilité et TE sont distinguées.
7. Réduction ciblée : ventes seules de positions actions longues vers le cash USD,
   objectif TE ≤ TE_initiale/2. Recherche des sous-ensembles par nombre croissant
   de lignes, résolution quadratique convexe sur chaque sous-ensemble. Une ligne
   allégée compte pour une transaction ; ni lots entiers, frais, fiscalité, marchés
   fermés, liquidité, ni exécution réelle ne sont modélisés. Les sorties donnent
   des réductions de poids, jamais des ordres ou quantités.
8. La borne affine tangente du problème convexe certifie les rejets à tolérance
   numérique indiquée. Aucun échec du solveur ne prouve l'impossibilité. Limite de
   5 000 sous-ensembles, configurable par `--max-subsets` ; arrêt sans prétention de
   minimum si la recherche est incomplète. Pour 11 titres, il y a au plus 2 047
   sous-ensembles. « Minimum » concerne le nombre de lignes, pas le montant vendu.
9. Calendrier : jusqu'aux 15 plus grosses positions actions réellement détenues,
   événements disponibles à `as_of_date` et datés d'ici au 13/11/2026 inclus. Une
   absence de date signifie information indisponible, jamais absence de résultats.

## Contraintes facultatives

Le fichier `rules.json` peut exprimer `source`, `long_only`, `max_weight`,
`min_cash_weight`, `max_cash_weight`, `max_gross_weight`, `max_one_way_turnover`,
et les dictionnaires `sector_caps`, `country_caps`, `currency_caps`. Toutes les
valeurs sont des fractions, sauf l'exposition brute. Toute clause non prise en
charge bloque plutôt que d'être ignorée. Cela ne vaut jamais certification d'un
règlement dont certaines clauses n'auraient pas été fournies.

Sans règlement : seules les vérifications de base s'appliquent (portefeuille long,
cash non négatif, poids total 1 et exposition brute ≤1). L'état des contraintes du
challenge reste `not_supplied`. La réduction ciblée recontrôle les règles fournies ;
si une autre amplitude de vente pourrait être nécessaire, elle ne prétend pas
avoir exclu la faisabilité du sous-ensemble. Elle peut donc rester non résolue
sous des contraintes supplémentaires plutôt que fournir un faux minimum.

## Sorties privées

`RAPPORT.md` court, `contributions.csv` exhaustif, `valuation.csv`, `earnings.csv`
et `run_manifest.json` avec empreintes des entrées, du code, de la covariance et
des sorties. Un calcul bloqué n'émet que le rapport de blocage et son manifeste,
avec code retour 2 et **aucune TE ni proposition chiffrée d'allègement**.

Références primaires : [Ledoit-Wolf, scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html),
[solveur SLSQP, SciPy](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html).
