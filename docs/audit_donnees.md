# Ce que contiennent nos exports WLS

**La prochaine étape est d'importer un seul fichier et de vérifier les données.**
Les deux Excel donnent une photographie de 6 857 titres, avec des indicateurs qui
se terminent au 2 octobre 2026. Pour un backtest, il faudra aussi leurs historiques.

Cet audit a été fait le 4 octobre 2026 sur toutes les valeurs enregistrées.
Les fichiers d'origine sont restés intacts. Les résultats n'ont pas été actualisés
sur le Terminal Bloomberg et les macros n'ont pas été exécutées.

Le premier import est maintenant implémenté sur la branche `codex/python-import-wls`.
Il retrouve les 6 857 titres, les trois volatilités manquantes et les cinq titres
dont les rendements sont identiques sur les trois horizons. Les données dérivées
restent dans `data/interim/`, avec leur provenance ; les conventions financières
sont toujours à confirmer.

## Les deux fichiers se ressemblent mais diffèrent

Ils contiennent exactement les mêmes titres, dans le même ordre, mais **4 748 lignes
ont au moins une valeur différente**. Il reste 2 109 lignes identiques.
Il faut choisir une version pour l'import, pas additionner les deux tables.

Je recommande de commencer avec `wls.xlsx`, feuille `WLSIndexData`, colonnes A à G.
Cette table contient des valeurs statiques, faciles à lire hors Terminal.
Gardons `WLS.xlsm` pour retrouver la requête BQL et comparer les résultats.
Ce choix est provisoire : le `.xlsx` n'est pas automatiquement la version la plus juste.

Le `.xlsm` conserve une requête qui sélectionne les membres du WLS avec un turnover
au moins égal à 500 millions dans les unités du champ. Nous avons donc un univers
filtré. La date historique des membres et celle du dernier prix ne sont pas fixées
explicitement dans cette requête.

## Les données qu'on peut déjà explorer

| Colonne | Contenu | Usage possible |
|---|---|---|
| A | Identifiant Bloomberg complet | Relier les tables et reconnaître chaque titre |
| B | Dernier prix | Préparer un snapshot, après confirmation de sa date et de sa devise |
| C | Turnover du 2 septembre au 2 octobre | Étudier la liquidité, après confirmation de l'unité et du calcul |
| D | Rendement passé sur un mois | Explorer un signal de court terme |
| E | Rendement passé sur trois mois | Explorer un signal de moyen terme |
| F | Rendement passé sur six mois | Explorer un signal plus long |
| G | Volatilité sur trois mois | Explorer le risque de chaque titre |

Les rendements sont calculés avec `side=BID`. La volatilité utilise
`tr_base=PRICE_IF_AVAILABLE`. Ces options sont à confirmer avec Data sur le Terminal.

Pour les unités, un exemple : la valeur 0,1502869 correspondrait à 15,03 % si elle
est exprimée en fraction. Il faut le vérifier avant toute conversion, même si
l'en-tête Bloomberg contient `display_returns=PERCENT`. Les cellules Excel sont
au format `General`, sans indication supplémentaire.

## Les contrôles ont trouvé peu de valeurs manquantes

Les 6 857 identifiants sont renseignés et distincts. Il n'y a aucun doublon de ligne,
aucune cellule vide dans la table, ni prix ou turnover nul ou négatif. Les trois
rendements sont numériques sur toutes les lignes. Les identifiants comportent
55 codes de marché différents ; cela ne permet pas de compter les pays.

Il manque seulement trois volatilités, sous forme d'erreurs `#N/A`, dans les deux fichiers :

| Titre | Cellule |
|---|---|
| `641A JT Equity` | G2169 |
| `642A JT Equity` | G2170 |
| `VYLR UN Equity` | G6686 |

Il reste donc **6 854 lignes complètes**. À l'import, conservons ces trois titres
avec une valeur manquante et un motif. Mettre zéro ferait croire qu'ils sont sans risque.

Cinq titres ont le même rendement à un, trois et six mois : `3718 TT Equity`,
`641A JT Equity`, `642A JT Equity`, `646A JT Equity` et `VYLR UN Equity`.
Un historique trop court est une explication possible. Vérifions leur première
date disponible avant d'utiliser ces trois horizons.

## Les vérifications à faire avec Data

Le turnover mérite une vérification rapide : sa médiane dépasse 2,46 milliards et
son maximum 876 milliards dans les valeurs enregistrées. Avant d'en faire une
mesure de volume quotidien en USD, confirmons le champ, l'unité et le rôle de `avg`.

Les devises des prix ne sont pas renseignées. Un prix de 2 785 000 sur un marché
ne peut pas être comparé directement à un prix de 10 sur un autre. Vérifions aussi
l'annualisation de la volatilité, les événements sur titres et quelques valeurs extrêmes.

Enfin, les écarts entre les fichiers dépassent parfois les arrondis. Pour `TXG UW Equity`,
le rendement six mois vaut 3,108374 dans le `.xlsx` et 3,164801 dans le `.xlsm`.
Des actualisations à des moments différents pourraient l'expliquer, mais la cause
n'est pas établie. Il faudra figer les prochains exports avec un horodatage clair.

## Ton premier chantier concret

1. Importer `wls.xlsx` avec la feuille et les colonnes explicites.
2. Renommer les colonnes pour les rendre lisibles, en gardant les valeurs d'origine.
3. Signaler les trois volatilités manquantes et les cinq historiques à vérifier.
4. Garder le fichier source, son empreinte et les périodes de calcul avec la table.

À la fin, on doit obtenir une table de 6 857 lignes, une liste courte d'anomalies et
un dictionnaire qui explique chaque colonne. Les données dérivées iront dans
`data/interim/`, puis dans `data/processed/` une fois les conventions confirmées.

Pendant ce temps, Data peut extraire les prix ou rendements historiques, les devises,
le benchmark et les compositions historiques. De ton côté, tu peux préparer le
moteur de backtest sur des données inventées dont le résultat est connu : prix
constants, hausse simple, frais d'une transaction et cash résiduel.

## Ce qu'il manque pour appliquer le README

| Travail | Données encore nécessaires |
|---|---|
| Elastic Net et mesure de l'IC | Plusieurs dates par titre, variables connues à chaque date et rendement futur relatif à cinq semaines |
| Momentum 12-1 | Au moins douze mois d'historique pour chaque date de calcul |
| Covariance Ledoit-Wolf | Rendements par date et titre en USD ; une volatilité seule ne donne pas les corrélations |
| Optimisation face au WLS | Alphas validés, covariance, poids du benchmark et frais |
| Backtest historique | Séries de prix, univers historiques, benchmark, devises et règles d'exécution |

Les trois rendements passés finissent à la même date. Ils ne forment pas trois
observations successives et ne donnent pas le rendement futur à cinq semaines.
Les variables d'analystes, de résultats, de valeur et de qualité ne sont pas présentes.
Il manque aussi les poids du WLS et sa série de performance.

Pour l'extraction historique, prévoyons assez de recul pour calculer les indicateurs,
entraîner les modèles et garder une période séparée pour les évaluer. Retenir
seulement les titres présents aujourd'hui fausserait la sélection historique.

## Annexe pour retrouver les chiffres

### Les feuilles des classeurs

| Fichier et feuille | Ce qu'on y trouve |
|---|---|
| `.xlsx` / `WLSIndexData` | La table utile en A1:G6858, sans formule dans les cellules |
| `.xlsm` / `DataWLS` | La table utile en A1:G6858 et la requête BQL en A1 ; l'étendue déclarée va jusqu'à AJ |
| `.xlsm` / `RefItems` | Feuille masquée, liste de champs d'un ancien modèle d'assurance ; trois résultats `#REF!` |
| `.xlsm` / `Help` | Aide d'un modèle Takaful Insurance Fundamentals, sans données WLS supplémentaires |
| `.xlsm` / `VersionChecker` | Feuille très masquée ; formule RTD Bloomberg avec un résultat `#N/A` |

Le `.xlsx` garde deux anciens liens externes et 14 noms définis contenant `#REF!`.
Le `.xlsm` garde un projet VBA et 17 noms définis, dont 14 avec `#REF!`. Ces résidus
ne sont pas des données fondamentales pour les titres. L'import doit se limiter à
la table utile. Le code VBA n'a pas été audité.

### Les valeurs de wls.xlsx

Valeurs brutes, sans conversion. Les trois erreurs sont exclues des statistiques
de volatilité. Tous les nombres sont finis ; les volatilités disponibles sont positives
et aucun rendement enregistré n'est inférieur ou égal à -1.

| Variable | Minimum | Médiane | 95e percentile | Maximum |
|---|---:|---:|---:|---:|
| Prix | 0,115 | 71,32 | 15 145,80 | 2 785 000 |
| Turnover | 500 199 963 | 2 462 316 830 | 28 032 512 607 | 876 562 943 742 |
| Rendement 1 mois | -0,874963 | -0,031447 | 0,196381 | 1,377067 |
| Rendement 3 mois | -0,945778 | -0,023566 | 0,370882 | 2,324715 |
| Rendement 6 mois | -0,962600 | 0,040779 | 0,895083 | 6,909683 |
| Volatilité 3 mois | 0,016297 | 0,374022 | 0,911889 | 3,626454 |

Le `.xlsm` a des médianes proches : prix 71,36 ; turnover 2 461 340 698,73 ;
rendements -0,031276 / -0,023370 / 0,040624 ; volatilité 0,374132.
Ses rendements maximums à un et six mois sont 1,402667 et 6,962756.

Pour vérifier les extrêmes sur le Terminal : `298040 KP Equity` pour le prix,
`AGL UN Equity` et `HEDEF TI Equity` pour les rendements, `MRNA UW Equity` et
`SDR LN Equity` pour la volatilité. Gardons ces valeurs tant que leur cause n'est pas connue.

### Les différences entre les versions

| Champ | Cellules différentes | Plus grand écart absolu |
|---|---:|---:|
| Prix | 2 170 | 173 |
| Turnover | 4 748 | 766 088 145,45 |
| Rendement 1 mois | 2 177 | 0,025600 |
| Rendement 3 mois | 2 173 | 0,032299 |
| Rendement 6 mois | 2 173 | 0,056426 |
| Volatilité 3 mois | 2 172 | 0,016776 |

Au total, 15 613 cellules numériques diffèrent. Les comparaisons ont été faites
sur toutes les lignes, pas sur un échantillon.

### Les sources de cet audit

Les valeurs, formules, feuilles masquées, noms définis, liens et textes des objets
graphiques ont été lus. Les tailles sont 688 687 octets pour `wls.xlsx` et
1 466 697 octets pour `WLS.xlsm`. Leurs dates de modification internes sont le
2 octobre 2026 à 16:49:08 et 16:28:12, sans fuseau établi ni garantie sur l'heure
effective des données.

Empreintes SHA-256 des copies analysées :

- `wls.xlsx` : `d8de4b5af0f06da31364070a12a33a293135c2c8a4b52e01e165e54a08b7f8bc`
- `WLS.xlsm` : `d5aff80116b41c5a5cc452926eee43831b946f1cc37174a64923fb95e50d6f48`
