# Optimisation robuste : étude et proposition pour le quant lab

État au **7 octobre 2026**, branche `codex/robust-optimization`.
Ce document propose une architecture ; il ne décrit pas un moteur déjà opérationnel.
Les recommandations ci-dessous sont notre jugement pour ce dépôt et ce délai,
pas une promesse de surperformance issue de la littérature.

## Décision proposée

Construire une **optimisation convexe à une période**, avec trois protections :

1. Une prévision d'alpha réduite selon sa fiabilité, avec une pénalité d'incertitude
   ellipsoïdale plutôt qu'une confiance totale dans les estimations.
2. Une covariance stabilisée et un risque mesuré **contre le WLS réel**, y compris
   quand notre univers d'investissement ne contient qu'une partie de l'indice.
3. Des limites d'exposition, des frais, puis une vérification indépendante des
   quantités exécutables et du cash.

Pour lundi : un univers limité et liquide, un signal simple explicitement assumé
comme provisoire, un portefeuille de référence à tracking error minimale et une
petite inclinaison active si elle résiste aux contrôles. Un Elastic Net réellement
validé est une deuxième livraison si les données historiques point-in-time ne
sont pas disponibles à temps. Un optimiseur ne crée pas un signal prédictif.

La page publique annonce le WLS Price Return Index et un début le 12 octobre à
9 h New York, soit 15 h Paris. Les Terms & Conditions transmis ensuite par
l'équipe définissent le critère comme le **Relative P&L calculé par TMSG**.
Sa formule exacte doit être relevée dans `TMSG → Help → Calculations`, plutôt
que remplacée par notre propre définition de rendement relatif.
[Bloomberg for Education](https://portal.bloombergforeducation.com/trading_challenges/13).

Les pièces fournies confirment le budget de 1 M USD, long-only, sans levier,
actions WLS uniquement et aucun ETF. Le mail autorise un déploiement partiel,
mais les Terms exigent le déploiement complet en première semaine. Le plan
retient provisoirement l'exigence complète et la première échéance annoncée,
vendredi 16 octobre à 22 h Paris. Les contradictions, la mécanique `TMSG` et
les confirmations encore nécessaires figurent dans `regles_challenge_2026.md`.

## 1. Ce que « robuste » signifie ici

Le risque est la variabilité des rendements ; l'incertitude d'estimation concerne
les paramètres que nous donnons à l'optimiseur. Les deux nécessitent des objets
différents : `Sigma` pour les rendements et `Omega` pour les erreurs d'alpha.
Une matrice de risque stabilisée ne démontre pas que les prévisions sont justes.

Goldfarb et Iyengar fondent l'approche par ensembles d'incertitude et certaines
reformulations coniques ; ils ne calibrent pas les signaux de notre équipe.
[Goldfarb et Iyengar, 2003](https://pubsonline.informs.org/doi/10.1287/moor.28.1.1.14260).

## 2. Comparaison des méthodes

| Méthode | Protection | Intérêt pour nous | Décision proposée |
|---|---|---|---|
| Alpha robuste ellipsoïdal + risque actif | Erreurs corrélées de prévision | Formulation convexe, cohérente avec le README | Méthode principale |
| Incertitude avec budget Gamma | Nombre/intensité de prévisions pouvant décevoir | Alternative interprétable à l'ellipsoïde | Comparaison après la V1 |
| Plusieurs matrices de risque | Sensibilité à la fenêtre et au régime | Conserve une formulation convexe avec matrices PSD | Deuxième protection, après V1 |
| CVaR relative et scénarios de stress | Pertes relatives dans les queues | Complète la tracking error | Rapport de stress dès V1 ; contrainte ensuite |
| DRO Wasserstein | Incertitude sur toute la distribution | Puissant mais exige un rayon d'ambiguïté défendable | Recherche après lancement |
| Black-Litterman | Combine prior et vues selon leur confiance | Utile si les vues sont structurées et calibrées | Alternative pour l'alpha, pas indispensable lundi |
| Tracking error minimale | N'exige aucun alpha | Référence, repli si signaux non fiables | Obligatoire dans les comparaisons |
| Équipondération, HRP, risk parity | Diversification avec peu de confiance dans les moyennes | Bons témoins ; risque absolu distinct du risque relatif | Comparaisons, pas remplacement automatique |

### 2.1 Alpha robuste ellipsoïdal

Sur un univers complet et des poids actifs `a = w - b`, poser
`alpha = alpha_hat + L_alpha u`, avec `||u||₂ <= kappa` et
`Omega = L_alpha L_alphaᵀ`. Alors le pire alpha est
`alpha_hatᵀ a - kappa ||L_alphaᵀ a||₂`.

L'orientation du facteur compte : un Cholesky `L` satisfait `LLᵀ = Omega` ;
utiliser `Lᵀa`, pas `La`. Une racine symétrique convient aussi. `Omega` doit
représenter l'erreur de prévision au même horizon que l'alpha, et non être
remplacée automatiquement par la covariance des rendements. Sans erreurs
hors échantillon, un choix diagonal conservateur reste une hypothèse, à nommer
comme telle. Une confiance trop faible ramènera vers la référence.
Cette reformulation reprend le principe des ensembles ellipsoïdaux de
[Goldfarb et Iyengar](https://pubsonline.informs.org/doi/10.1287/moor.28.1.1.14260).

### 2.2 Incertitude avec budget Gamma

Bertsimas et Sim permettent de moduler le conservatisme par un budget
d'incertitude. Pour notre adaptation, borner chaque erreur par `d_i` et limiter
la somme des intensités d'erreur par `Gamma`. La pénalité devient le maximum
de `sum(d_i |a_i| z_i)` avec `0 <= z_i <= 1` et `sum(z_i) <= Gamma`.
Sa dualisation donne des contraintes linéaires.

Avantage : ne pas supposer que toutes les prévisions se dégradent simultanément.
Limite : les amplitudes et le budget restent à estimer. Avec des poids long-only,
des rayons identiques et un budget couvrant tous les actifs, une pénalité en
`||w||₁` est constante ; elle n'apporte aucune diversification. L'exposition
active ou des rayons différenciés évitent de confondre robustesse et constante.
[Bertsimas et Sim, 2004](https://www.mit.edu/~dbertsim/papers/melvyn/The-Price-Of-Robustness-OR52.pdf).

### 2.3 Covariance stabilisée et plusieurs modèles de risque

Le module existant utilise `sklearn.covariance.LedoitWolf`. Sa cible est
l'identité redimensionnée par la variance moyenne ; ce n'est pas exactement
la cible à corrélation constante de l'article « Honey ». Conserver le module et
tester sa stabilité. [Documentation scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.ledoit_wolf.html).

Le shrinkage atténue les erreurs de covariance qui perturbent les allocations.
Cela motive l'estimation stabilisée déjà choisie, sans établir que notre
implémentation ou nos données reproduiront les performances du papier.
[Ledoit et Wolf](https://ledoit.net/honey.pdf).

Proposition propre au lab : comparer la fenêtre récente à une fenêtre plus longue
et à un régime stressé, sur **les mêmes titres et les mêmes unités**. Exiger
`||F_j x||₂ <= tau_j` pour chaque matrice jointe PSD `C_j = F_jᵀ F_j`.
L'intersection reste convexe. Limiter le nombre de modèles ; des scénarios
contradictoires peuvent rendre les contraintes impossibles à satisfaire.
Le minimum réalisable de tracking error doit être calculé avant de choisir `tau`.

Un modèle factoriel `Sigma = B Sigma_f Bᵀ + D` pourra accélérer les calculs à
grande dimension. Les exemples du groupe CVX montrent l'avantage de cette
structure. Dans notre cas, les expositions pays/devise ne sont pas encore fournies
et des composantes principales doivent être estimées uniquement sur le passé.
[CVX Short Course](https://www.cvxgrp.org/cvx_short_course/docs/applications/notebooks/portfolio_optimization.html).

Pour la saisie manuelle, distinguer candidats analysés et positions retenues.
Une proposition de lancement est d'étudier 200 à 500 candidats puis une liste
de l'ordre de 20 à 40 positions, représentative des secteurs et zones disponibles.
Ces nombres sont des objectifs opérationnels à valider, pas des limites du
challenge. La présélection doit annoncer sa perte de couverture et de TE minimale.
Après réduction de l'univers, **résoudre à nouveau** les contraintes : supprimer
des petits poids et renormaliser ne garantit pas leur respect. La cardinalité
exacte serait non convexe ; elle n'est pas requise pour la première livraison.

### 2.4 CVaR relative et stress

Avec des pertes relatives `loss_s = r_b,s - r_sᵀ w`, la formulation empirique
est `min_eta eta + sum(max(loss_s - eta, 0)) / ((1-q) S)`.
Des variables auxiliaires transforment ce calcul en programme linéaire pour des
scénarios affines. La CVaR est un critère de queue, pas une garantie de perte
maximale. [Rockafellar et Uryasev](https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf).

Application proposée : évaluer les mêmes poids sous marchés baissiers, choc
sectoriel, choc FX et frais doublés. Distinguer scénarios historiques et scénarios
inventés. Avec seulement 52 observations, une queue à 95 % représente environ
2,6 observations : ne pas présenter cette estimation comme précise. Pour les
fenêtres de cinq semaines, l'effectif indépendant est encore plus faible.

### 2.5 DRO Wasserstein

Esfahani et Kuhn optimisent contre la pire distribution dans une boule
Wasserstein autour de l'échantillon et obtiennent des problèmes convexes sous
des hypothèses spécifiées. Les garanties statistiques du papier dépendent de
ces hypothèses ; elles ne se transfèrent pas automatiquement à nos séries
temporellement dépendantes. [Article des auteurs](https://arxiv.org/abs/1505.05116).

Pour notre délai, le rayon de la boule, le choix de distance, la dimension et la
validation temporelle sont trop importants pour une mise en production improvisée.
Une DRO est une candidate pour la suite, pas un prérequis des premiers trades.

### 2.6 Priors, contraintes et portefeuilles simples

Black-Litterman combine un prior de marché et des vues avec une incertitude
explicite. Il pourrait régulariser des vues sectorielles ou des alphas ; les poids
de marché seuls ne donnent pas un prior correctement calibré. Éviter le double
comptage de la même incertitude dans le posterior et la pénalité robuste.
[Black et Litterman, 1992](https://rpc.cfainstitute.org/research/financial-analysts-journal/1992/faj-v48-n5-28).

Les contraintes de poids peuvent agir comme régularisation face aux erreurs
d'estimation. Cela soutient des limites de concentration, sans justifier un seuil
universel pour notre challenge. [Jagannathan et Ma](https://www.nber.org/system/files/working_papers/w8922/w8922.pdf),
[DeMiguel et al., contraintes de normes](https://pubsonline.informs.org/doi/10.1287/mnsc.1080.0986).

Les résultats de DeMiguel, Garlappi et Uppal motivent une comparaison exigeante
avec une allocation simple ; aucun optimiseur sophistiqué ne mérite un privilège
sans validation hors échantillon. [Article 2009](https://moodle.novasbe.pt/pluginfile.php/664905/mod_folder/content/0/Articles/DeMiguel_Garlappi_Uppal_2009.pdf?forcedownload=1).

HRP utilise la structure hiérarchique des corrélations pour construire une
allocation diversifiée. Pour nous, sa focalisation sur la diversification du risque
ne remplace pas les contraintes de WLS, de frais et d'exposition active.
[López de Prado, 2016](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678).

## 3. Le piège du benchmark partiellement couvert

Notre historique couvre 1 262 titres, représentant **84,1704 %** des poids actuels
du WLS. Renormaliser ces poids à 100 % crée un **autre benchmark**. Ce portefeuille
de sous-univers peut servir de référence investissable, mais pas de WLS officiel.

Proposition de modélisation pour le dépôt : estimer conjointement les rendements
des titres et du WLS officiel, avec les mêmes dates, devise et convention.

```text
       [ Sigma    q  ]
C  =   [ qᵀ       v  ],     x = [ w ; -1 ]

q = Cov(r_titres, r_WLS) ; v = Var(r_WLS)
TE_week² = xᵀ C x = wᵀ Sigma w - 2 qᵀ w + v
```

Le calcul par `C = Fᵀ F` et `||F x||₂` garde la tracking error sous forme convexe
sans devoir investir dans chaque constituant. La matrice jointe doit rester PSD ;
ne pas estimer ses blocs indépendamment et les assembler sans vérification.
Un shrinkage joint peut biaiser les covariances croisées : comparer sa tracking
error aux résidus réellement observés et à un modèle factoriel.

Deux options d'alpha :

- Pour les rendements relatifs attendus `d_i = E[r_i - r_WLS]`, le rendement actif
  attendu est `dᵀ w` si les poids actions totalisent 1. La pénalité robuste devient
  `kappa ||L_dᵀ w||₂`. Le benchmark est inclus dans la définition et l'incertitude
  de `d`. Avec du cash, cette simplification doit être étendue.
- Pour des vues autour d'une référence investissable `b_ref`, utiliser
  `alphaᵀ(w-b_ref)` et sa pénalité active. Nommer ce prior comme référence de
  sous-univers ; contrôler séparément le risque contre le vrai WLS.

Ne pas mélanger silencieusement ces deux contrats. Le choix dépendra du signal
livré. Les objectifs relatifs sur une période ne reproduisent pas exactement le
classement de rendement composé sur tout le challenge ; celui-ci doit être
calculé séparément dans le suivi.

## 4. Formulation V1 proposée

Pour un portefeuille actions entièrement investi et des alphas relatifs `d` :

```text
maximize    d_hatᵀ w - kappa ||L_dᵀ w||₂
            - lambda xᵀ C x
            - sum_i c_i |w_i - w_prev,i|

subject to  sum(w) = 1 ; 0 <= w_i <= cap_i
            ||F x||₂ <= tau_week
            bornes sectorielles / pays / devises, lorsqu'elles sont renseignées
            bornes de liquidité et de rotation compatibles avec le premier achat
```

Cette formulation est une proposition à valider avec l'équipe. `lambda` peut
être nul si la contrainte de TE suffit ; ajouter une préférence pour la référence
comme départage évite des solutions arbitraires sans signal. Les limites de
secteur/pays doivent se comparer au **WLS complet**, pas aux seuls actifs retenus.
Le bêta relatif doit viser une exposition proche de 1 au benchmark, et non une
neutralité de marché à bêta 0 dans un portefeuille long-only.

Les Terms confirment le plafond de 20 % du notional, soit 200 000 USD au départ ;
18 % est notre plafond interne indiqué dans le README. Confirmer avec TMSG le
traitement des mouvements de marché et de plusieurs idées sur le même émetteur.
Un plafond interne plus bas
pour la V1 peut être étudié, mais n'est pas encore une décision d'équipe.
Ne pas fixer `tau`, `kappa` ou les budgets de secteur sans test de faisabilité et
analyse de sensibilité.

### Unités et horizon

Les alphas du README ciblent cinq semaines ; la covariance actuelle est
hebdomadaire. `Omega` porte sur l'erreur à l'horizon du signal ; les frais sont
payés à chaque exécution. Comparer des termes au même horizon, ou expliquer
explicitement les conversions. `TE_annual ≈ sqrt(52) TE_week` et
`Sigma_5w ≈ 5 Sigma_week` supposent une structure temporelle appropriée ; les
autocovariances et la composition des rendements peuvent invalider l'approximation.
Mesurer aussi les rendements composés sur cinq semaines dans les diagnostics.

### Frais, cash et quantités

`sum(c_i |delta_w_i|)` convient à des frais proportionnels par côté. La définition
de turnover doit indiquer s'il s'agit de la somme brute ou de sa moitié. Le
premier achat depuis le cash représente 100 % de notional acheté et n'est pas
une rotation ordinaire : une limite faible rendrait ce premier achat impossible.

Si les coûts sont prélevés sur le cash, ne pas exécuter naïvement des poids qui
consomment déjà tout le capital. Le convertisseur doit satisfaire
`notional_usd + commissions + cash_residuel <= capital_disponible`, tenir compte
des unités de prix (pence/GBP, etc.), des FX et des arrondis du simulateur. Le
handbook montre que les achats sont saisis en dollars et que TMSG calcule les
unités : l'export principal est un **ticket en USD**, les quantités sont des
estimations puis une réconciliation après exécution. Les frais ne sont pas
chiffrés dans les pièces reçues ; ne pas en inventer un barème.

Suivre cash disponible, cash réservé aux achats et crédits de vente en attente.
Le handbook annonce environ vingt minutes de traitement. Le parcours de vente
documenté est `Close Idea` : une vente partielle ou un rééquilibrage continu en
quantités ne doit pas être supposé possible. Ne pas activer stop-loss/take-profit
par défaut, puisqu'ils modifient automatiquement les positions hors du moteur.

La V1 vise un déploiement complet conforme aux Terms en première semaine, mais
le pipeline doit représenter le cash durant la construction et les exécutions.
Si des stratégies avec cash sont autorisées ensuite, étendre les poids par `c`,
imposer `sum(w)+c=1`, ajouter rendement/risque relatifs du cash au modèle et
recalibrer la comparaison au WLS. Garder le cash ne signifie pas risque actif nul.

## 5. Calibration et sélection

1. Fixer un portefeuille investissable de référence et mesurer sa TE minimale.
2. Construire les scores sur les informations connues avant la décision ; un rang
   n'est pas encore un alpha en pourcentage.
3. Quand les historiques de variables existent : walk-forward purgé sur cinq
   semaines, transformations estimées sur le train, hyperparamètres choisis dans
   une validation intérieure. Séparer la période finale de jugement.
4. Estimer l'erreur des prévisions hors échantillon, avec régularisation. Les
   fenêtres à cinq semaines se chevauchent ; bootstrap par blocs ou évaluation
   sur fenêtres espacées, pas tirage indépendant des lignes.
5. Comparer quelques niveaux de robustesse et de TE préfixés ; retenir une zone
   stable de résultats et de poids, pas le meilleur point d'une grande grille.
6. Juger rendement relatif net, TE réalisée, pertes relatives, rotation et stabilité.
   Une estimation de `P(battre WLS)` est conditionnelle au modèle et doit avoir
   une incertitude ; le top 5 % dépend aussi des autres équipes.

Sans panel point-in-time, utiliser un signal exploratoire simple : momentum
12-1 calculé sur des prix validés, complété éventuellement de rangs de révisions
et qualité du snapshot après traitement de la couverture et des EPS négatifs.
Les coefficients d'un composite ne seront pas présentés comme appris ou validés.
Limiter ses inclinaisons actives et comparer systématiquement à la référence.
L'estimation `alpha = IC × sigma × z` n'est exploitable qu'après choix explicite
du type d'IC, de l'horizon, du score et de son incertitude ; ne pas inventer un IC.

## 6. Implémentation et contrats proposés

Commencer directement avec **CVXPY et CLARABEL** pour les normes et contraintes
coniques ; OSQP reste une option pour un problème purement quadratique. SCS peut
servir de vérification secondaire. Un statut `optimal_inaccurate` demande une
revérification des résidus, pas une génération automatique d'ordres.
[Documentation des solveurs CVXPY](https://www.cvxpy.org/tutorial/solvers/index.html).

Le cadre de Boyd et al. sépare prévisions, risque, coûts et décisions et traite
la planification multi-période. Nous reprenons cette séparation ; la V1 restera
à une période car les prévisions futures et les états de portefeuille ne sont
pas encore disponibles. [Boyd et al., 2017](https://stanford.edu/~boyd/papers/cvx_portfolio.html).

| Module à ajouter | Entrée essentielle | Sortie essentielle |
|---|---|---|
| `market_data.py` | Exports, métadonnées, FX, calendrier | Prix comparables et rendements alignés, exclusions motivées |
| `signals.py` | Variables datées / signaux | Scores, alpha, statut de validation, incertitude |
| `risk_relative.py` | Rendements titres + WLS | Covariance jointe, facteur, diagnostics |
| `optimisation.py` | Alpha, risque, contraintes, positions actuelles | Poids, statut, faisabilité, décomposition de l'objectif |
| `orders.py` | Poids, positions/idées, prix/FX/frais et ordres en attente | Tickets BUY en USD / CLOSE par idée, quantités estimées, cash et contrôles |
| `backtest.py` | Décisions décalées, règles d'exécution | NAV, benchmark, relatif net, frais, turnover |
| `run_lab.py` | Configuration et date de décision | Dossier d'exécution reproductible, rapport et ordres proposés |

Les noms sont des interfaces proposées, pas des fichiers déjà présents. Préserver
`covariance.py` : l'adaptateur doit utiliser exactement les actifs renvoyés par le
module et réordonner tous les autres objets par identifiant. Aucun alignement
par position implicite, aucune colonne manquante remplie par zéro.

Un run conserve les empreintes sources, date/heure de données et décision, version
Git, configuration, exclusions, modèle, diagnostics solveur, poids et contrôles
après arrondi. Il produit des tickets **proposés**, que l'équipe vérifie puis que
**seul le capitaine** saisit dans `TMSG` ; la recherche actuelle ne réalise aucun trade.

## 7. Tests utiles avant utilisation

- Référence répliquée : TE nulle dans un exemple exact ; diagonale et racine avec
  `FᵀF=C`, permutation des tickers et matrice jointe non PSD.
- Incertitude : `kappa=0` retrouve le problème nominal ; augmenter l'incertitude
  réduit la valeur optimale pire cas, pas nécessairement chaque poids.
- Faisabilité : plafond × nombre d'actifs, secteurs sans actif, TE sous le minimum,
  blocage explicite et absence d'ordres si solveur échoue.
- Alignement : prix périmés, mauvaise devise, dates futures, NaN, doublons,
  covariance ne couvrant pas les positions détenues.
- Exécution : tickets USD, achat initial, frais, prix en sous-unités, arrondi TMSG,
  achat/vente en attente, clôture d'idée et prévention des doubles saisies ;
  limites revérifiées sur les positions réalisées et coûts.
- Backtest : prix constants, hausse connue, achat puis vente avec frais, cash et
  FX, décision après clôture exécutée au prochain prix autorisé, sans anticipation.
- Comparaison : référence à TE minimale, équipondération et optimisation nominale
  sur le même univers, les mêmes dates et les mêmes coûts.

Le lab est aujourd'hui testé pour l'import et la covariance, pas pour cette chaîne
complète. Les seuils, signaux et données devront être figés avant les décisions
réelles. La livraison détaillée avant lundi figure dans `plan_lancement_lundi.md`.
