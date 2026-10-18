# Protocole IC conditionnel — v1.0

Préenregistrement du 18 octobre 2026, branche research/macro-conditional-ic. Ce document, les 200 lignes de MDE_IC_CONDITIONNEL.csv, INPUTS_IC_CONDITIONNEL.json, le code et les tests seront figés par le tag annoté **protocol-ic-v1.0** puis poussés AVANT toute moyenne d'IC par étiquette. Aucun IC conditionnel n'a été consulté pendant la rédaction ni le calcul de puissance.

## 1. Question et données fixées

H0 : l'IC moyen est identique quand une étiquette macro est vraie ou fausse. Contraste bilatéral Δ = moyenne(IC | vrai) − moyenne(IC | faux). Association historique exploratoire ; aucune causalité, règle de portefeuille, optimisation, rendement ou ordre n'est testé.

Les archives par titre initiales ne couvrent qu'un offset Elastic Net ; le score combiné n'est archivé qu'au 02/10/2026 sans cible réalisée. L'utilisateur a explicitement autorisé le 18/10/2026 la régénération historique des deux scores avec le code cinq semaines figé, sans modification de quant-lab. Les IC agrégés de validation ne remplacent pas les scores combinés manquants.

Panel sauvegardé : features_weekly_v1.csv.gz, SHA256 **62f13e8cd8ed1ac5a38bf1808ff8b25b026e7922f2860c002ed4276346686ece**. Code cœur figé : **1bda3897678168b1a980d44c3cddde892f417158** ; ses fichiers sont vérifiés avant ajustement. La cible future est lue directement dans **future_excess_return_5w**, jamais recalculée. Le module macro n'est pas un prédicteur de rendement.

Régénération : mêmes six features V1, ElasticNetConfig existant (trois ans, purge cinq semaines, pas cinq semaines, alpha=0,0005, l1_ratio=0,5, min_train_rows=20 000, min_test_rows=50) ; modèles existants make_model et make_tail_model ; aucune recherche d'hyperparamètres. Combiné = 0,75 × rang percentile Tail + 0,25 × rang percentile Elastic Net, rangs moyens par date et même univers évalué. Les cibles connues ne sont utilisées qu'en entraînement purgé et pour mesurer l'IC après prédiction. L'univers historique reste celui de l'ancienne préparation conditionnée à la disponibilité de la cible ; il n'est pas corrigé dans cette étude et ne prouve pas l'investissabilité passée.

Préparation avant le tag : **349983 lignes titre-date**, **608 IC inconditionnels** (deux scores × 304 dates), du **2020-11-06 au 2026-08-28**. Les fichiers de données restent dans outputs/macro_conditional_ic/prepared, ignorés par Git. Leurs empreintes exactes sont dans INPUTS_IC_CONDITIONNEL.json.

Étiquettes : sorties H strict avec/sans GPR/EPU validées à l'étape 05, issues exclusivement du cache 20261018T143956.868547Z. Source macro, code, états et percentiles inchangés ; limites PIT_APPROXIMATED et CONTEMPORARY_INPUT_RETRO_METHOD de GPR/EPU conservées. Les neuf étiquettes communes aux deux ablations ont été vérifiées identiques sur les dates retenues ; leurs tests sont donc dupliqués pour présentation, pas comptés comme preuves supplémentaires.

## 2. Calendrier et jointure stricte

Chaque offset utilise une date toutes les cinq semaines du calendrier V1 existant : 61 dates pour chacun des offsets 0–3, 60 pour l'offset 4. Le rendement cible couvre cinq semaines ; les horizons ne se chevauchent pas à l'intérieur d'un offset. Les cinq offsets se chevauchent entre eux et ne sont jamais additionnés comme des observations indépendantes.

Pour chaque date nominale de prédiction p, sélectionner la dernière ligne macro de séance NYSE s avec **s < p**, par jointure as-of arrière avec allow_exact_matches=False. Aucune jointure de même date, interpolation ni remplissage d'une étiquette inconnue par une étiquette antérieure. Conserver macro_date, prediction_date et offset pour audit. Les vendredis fériés restent les dates nominales des prédictions hebdomadaires du cœur ; la date macro est une séance strictement précédente.

IC par date : Spearman entre chaque score et la cible sauvegardée, sur les mêmes titres complets, rangs moyens en cas d'ex æquo. Un score ou une cible constante rend l'IC non estimable. Les dates d'IC non fini et les étiquettes NA sont exclues du contraste concerné, conservées dans le décompte d'exclusions. Aucun autre filtre ou sous-échantillon n'est exploré.

## 3. Effet minimal détectable — calcul antérieur aux contrastes

α familial = 5 %, puissance de planification = 80 %, test bilatéral. Famille fixée à **110** contrastes uniques : deux scores × onze étiquettes × cinq offsets. Les neuf étiquettes communes répétées dans l'ablation ne créent pas 90 tests supplémentaires. Bonferroni est fixé avant résultats ; α par contraste = 0,05/110. Aucune sélection de la meilleure étiquette ou du meilleur offset.

Pour chaque score et offset, σ est uniquement l'écart-type historique global des IC inconditionnels (ddof=1), sans partition macro. Pour chaque étiquette, n_vrai et n_faux sont comptés sur les dates d'IC valides et d'étiquette connue. Le code de puissance ne joint aux étiquettes que des dates/offsets : aucune valeur d'IC n'est disponible dans la table de comptage.

Formule fixée : **MDE = [z(1−α/(2×110)) + z(0,80)] × σ × √[2 × (1/n_vrai + 1/n_faux)]**. Le facteur 2 est une inflation de variance fixée pour le bloc bootstrap de deux observations, sans estimation à partir d'un contraste. MDE exprimé en points d'IC ; si un effectif est nul ou σ non positive/non finie : non estimable, données insuffisantes. C'est une approximation analytique de puissance sous variance homogène et dépendance courte, pas une garantie de puissance en présence de dépendance longue. Aucun effet moyen conditionnel n'intervient dans ce calcul.

Les valeurs numériques complètes ci-dessous sont aussi conservées sans arrondi dans MDE_IC_CONDITIONNEL.csv, dont l'empreinte est figée. Les effectifs insuffisants ont également leur MDE calculé si possible, à titre descriptif uniquement.

| Score | Ablation | Étiquette | Offset | n vrai | n faux | NA | σ global | MDE | ≥20 dans chaque groupe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elastic_net | with_news | INFLATION_HAUTE | 0 | 23 | 38 | 0 | 0.176280054 | 0.286351541 | True |
| elastic_net | with_news | INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.176280054 | 0.560644824 | False |
| elastic_net | with_news | RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.176280054 | 0.375474931 | False |
| elastic_net | with_news | RESSERREMENT | 0 | 16 | 45 | 0 | 0.176280054 | 0.315492466 | False |
| elastic_net | with_news | ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.176280054 | 0.779317155 | False |
| elastic_net | with_news | COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.176280054 | 0.289009152 | True |
| elastic_net | with_news | STRESS_CREDIT | 0 | 0 | 61 | 0 | 0.176280054 | non estimable | False |
| elastic_net | with_news | STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.176280054 | 0.435420969 | False |
| elastic_net | with_news | CHOC_ENERGIE | 0 | 17 | 44 | 0 | 0.176280054 | 0.309531207 | False |
| elastic_net | with_news | RISQUE_GEO_ELEVE | 0 | 35 | 26 | 0 | 0.176280054 | 0.280630289 | True |
| elastic_net | with_news | INCERTITUDE_ELEVEE | 0 | 41 | 20 | 0 | 0.176280054 | 0.295629871 | True |
| elastic_net | without_news | INFLATION_HAUTE | 0 | 23 | 38 | 0 | 0.176280054 | 0.286351541 | True |
| elastic_net | without_news | INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.176280054 | 0.560644824 | False |
| elastic_net | without_news | RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.176280054 | 0.375474931 | False |
| elastic_net | without_news | RESSERREMENT | 0 | 16 | 45 | 0 | 0.176280054 | 0.315492466 | False |
| elastic_net | without_news | ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.176280054 | 0.779317155 | False |
| elastic_net | without_news | COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.176280054 | 0.289009152 | True |
| elastic_net | without_news | STRESS_CREDIT | 0 | 0 | 61 | 0 | 0.176280054 | non estimable | False |
| elastic_net | without_news | STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.176280054 | 0.435420969 | False |
| elastic_net | without_news | CHOC_ENERGIE | 0 | 17 | 44 | 0 | 0.176280054 | 0.309531207 | False |
| elastic_net | with_news | INFLATION_HAUTE | 1 | 23 | 38 | 0 | 0.183660121 | 0.298339816 | True |
| elastic_net | with_news | INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.183660121 | 0.584116548 | False |
| elastic_net | with_news | RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.183660121 | 0.408292402 | False |
| elastic_net | with_news | RESSERREMENT | 1 | 17 | 44 | 0 | 0.183660121 | 0.322489913 | False |
| elastic_net | with_news | ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.183660121 | 0.668639932 | False |
| elastic_net | with_news | COURBE_INVERSEE | 1 | 22 | 39 | 0 | 0.183660121 | 0.301108690 | True |
| elastic_net | with_news | STRESS_CREDIT | 1 | 0 | 61 | 0 | 0.183660121 | non estimable | False |
| elastic_net | with_news | STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.183660121 | 0.376084633 | False |
| elastic_net | with_news | CHOC_ENERGIE | 1 | 16 | 45 | 0 | 0.183660121 | 0.328700743 | False |
| elastic_net | with_news | RISQUE_GEO_ELEVE | 1 | 37 | 24 | 0 | 0.183660121 | 0.295978695 | True |
| elastic_net | with_news | INCERTITUDE_ELEVEE | 1 | 40 | 21 | 0 | 0.183660121 | 0.304317754 | True |
| elastic_net | without_news | INFLATION_HAUTE | 1 | 23 | 38 | 0 | 0.183660121 | 0.298339816 | True |
| elastic_net | without_news | INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.183660121 | 0.584116548 | False |
| elastic_net | without_news | RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.183660121 | 0.408292402 | False |
| elastic_net | without_news | RESSERREMENT | 1 | 17 | 44 | 0 | 0.183660121 | 0.322489913 | False |
| elastic_net | without_news | ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.183660121 | 0.668639932 | False |
| elastic_net | without_news | COURBE_INVERSEE | 1 | 22 | 39 | 0 | 0.183660121 | 0.301108690 | True |
| elastic_net | without_news | STRESS_CREDIT | 1 | 0 | 61 | 0 | 0.183660121 | non estimable | False |
| elastic_net | without_news | STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.183660121 | 0.376084633 | False |
| elastic_net | without_news | CHOC_ENERGIE | 1 | 16 | 45 | 0 | 0.183660121 | 0.328700743 | False |
| elastic_net | with_news | INFLATION_HAUTE | 2 | 24 | 37 | 0 | 0.184050718 | 0.296608163 | True |
| elastic_net | with_news | INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.184050718 | 0.585358810 | False |
| elastic_net | with_news | RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.184050718 | 0.409160733 | False |
| elastic_net | with_news | RESSERREMENT | 2 | 18 | 43 | 0 | 0.184050718 | 0.317701381 | False |
| elastic_net | with_news | ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | 0.184050718 | 0.585358810 | False |
| elastic_net | with_news | COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.184050718 | 0.298974306 | True |
| elastic_net | with_news | STRESS_CREDIT | 2 | 0 | 61 | 0 | 0.184050718 | non estimable | False |
| elastic_net | with_news | STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.184050718 | 0.376884466 | False |
| elastic_net | with_news | CHOC_ENERGIE | 2 | 18 | 43 | 0 | 0.184050718 | 0.317701381 | False |
| elastic_net | with_news | RISQUE_GEO_ELEVE | 2 | 36 | 25 | 0 | 0.184050718 | 0.294624140 | True |
| elastic_net | with_news | INCERTITUDE_ELEVEE | 2 | 41 | 20 | 0 | 0.184050718 | 0.308661638 | True |
| elastic_net | without_news | INFLATION_HAUTE | 2 | 24 | 37 | 0 | 0.184050718 | 0.296608163 | True |
| elastic_net | without_news | INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.184050718 | 0.585358810 | False |
| elastic_net | without_news | RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.184050718 | 0.409160733 | False |
| elastic_net | without_news | RESSERREMENT | 2 | 18 | 43 | 0 | 0.184050718 | 0.317701381 | False |
| elastic_net | without_news | ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | 0.184050718 | 0.585358810 | False |
| elastic_net | without_news | COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.184050718 | 0.298974306 | True |
| elastic_net | without_news | STRESS_CREDIT | 2 | 0 | 61 | 0 | 0.184050718 | non estimable | False |
| elastic_net | without_news | STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.184050718 | 0.376884466 | False |
| elastic_net | without_news | CHOC_ENERGIE | 2 | 18 | 43 | 0 | 0.184050718 | 0.317701381 | False |
| elastic_net | with_news | INFLATION_HAUTE | 3 | 24 | 37 | 0 | 0.169077076 | 0.272477291 | True |
| elastic_net | with_news | INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.169077076 | 0.615548350 | False |
| elastic_net | with_news | RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.169077076 | 0.346859122 | False |
| elastic_net | with_news | RESSERREMENT | 3 | 18 | 43 | 0 | 0.169077076 | 0.291854447 | False |
| elastic_net | with_news | ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | 0.169077076 | 0.615548350 | False |
| elastic_net | with_news | COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.169077076 | 0.274650933 | True |
| elastic_net | with_news | STRESS_CREDIT | 3 | 0 | 61 | 0 | 0.169077076 | non estimable | False |
| elastic_net | with_news | STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.169077076 | 0.325045756 | False |
| elastic_net | with_news | CHOC_ENERGIE | 3 | 18 | 43 | 0 | 0.169077076 | 0.291854447 | False |
| elastic_net | with_news | RISQUE_GEO_ELEVE | 3 | 37 | 24 | 0 | 0.169077076 | 0.272477291 | True |
| elastic_net | with_news | INCERTITUDE_ELEVEE | 3 | 39 | 22 | 0 | 0.169077076 | 0.277199952 | True |
| elastic_net | without_news | INFLATION_HAUTE | 3 | 24 | 37 | 0 | 0.169077076 | 0.272477291 | True |
| elastic_net | without_news | INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.169077076 | 0.615548350 | False |
| elastic_net | without_news | RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.169077076 | 0.346859122 | False |
| elastic_net | without_news | RESSERREMENT | 3 | 18 | 43 | 0 | 0.169077076 | 0.291854447 | False |
| elastic_net | without_news | ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | 0.169077076 | 0.615548350 | False |
| elastic_net | without_news | COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.169077076 | 0.274650933 | True |
| elastic_net | without_news | STRESS_CREDIT | 3 | 0 | 61 | 0 | 0.169077076 | non estimable | False |
| elastic_net | without_news | STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.169077076 | 0.325045756 | False |
| elastic_net | without_news | CHOC_ENERGIE | 3 | 18 | 43 | 0 | 0.169077076 | 0.291854447 | False |
| elastic_net | with_news | INFLATION_HAUTE | 4 | 24 | 36 | 0 | 0.150081457 | 0.243182848 | True |
| elastic_net | with_news | INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.150081457 | 0.546627853 | False |
| elastic_net | with_news | RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.150081457 | 0.333644115 | False |
| elastic_net | with_news | RESSERREMENT | 4 | 16 | 44 | 0 | 0.150081457 | 0.269403655 | False |
| elastic_net | with_news | ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | 0.150081457 | 0.663683190 | False |
| elastic_net | with_news | COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.150081457 | 0.247221748 | True |
| elastic_net | with_news | STRESS_CREDIT | 4 | 0 | 60 | 0 | 0.150081457 | non estimable | False |
| elastic_net | with_news | STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.150081457 | 0.307889891 | False |
| elastic_net | with_news | CHOC_ENERGIE | 4 | 18 | 42 | 0 | 0.150081457 | 0.259973400 | False |
| elastic_net | with_news | RISQUE_GEO_ELEVE | 4 | 35 | 25 | 0 | 0.150081457 | 0.241649436 | True |
| elastic_net | with_news | INCERTITUDE_ELEVEE | 4 | 38 | 22 | 0 | 0.150081457 | 0.247221748 | True |
| elastic_net | without_news | INFLATION_HAUTE | 4 | 24 | 36 | 0 | 0.150081457 | 0.243182848 | True |
| elastic_net | without_news | INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.150081457 | 0.546627853 | False |
| elastic_net | without_news | RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.150081457 | 0.333644115 | False |
| elastic_net | without_news | RESSERREMENT | 4 | 16 | 44 | 0 | 0.150081457 | 0.269403655 | False |
| elastic_net | without_news | ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | 0.150081457 | 0.663683190 | False |
| elastic_net | without_news | COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.150081457 | 0.247221748 | True |
| elastic_net | without_news | STRESS_CREDIT | 4 | 0 | 60 | 0 | 0.150081457 | non estimable | False |
| elastic_net | without_news | STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.150081457 | 0.307889891 | False |
| elastic_net | without_news | CHOC_ENERGIE | 4 | 18 | 42 | 0 | 0.150081457 | 0.259973400 | False |
| combined | with_news | INFLATION_HAUTE | 0 | 23 | 38 | 0 | 0.195570707 | 0.317687521 | True |
| combined | with_news | INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.195570707 | 0.621997228 | False |
| combined | with_news | RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.195570707 | 0.416563850 | False |
| combined | with_news | RESSERREMENT | 0 | 16 | 45 | 0 | 0.195570707 | 0.350017392 | False |
| combined | with_news | ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.195570707 | 0.864599279 | False |
| combined | with_news | COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.195570707 | 0.320635961 | True |
| combined | with_news | STRESS_CREDIT | 0 | 0 | 61 | 0 | 0.195570707 | non estimable | False |
| combined | with_news | STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.195570707 | 0.483069895 | False |
| combined | with_news | CHOC_ENERGIE | 0 | 17 | 44 | 0 | 0.195570707 | 0.343403782 | False |
| combined | with_news | RISQUE_GEO_ELEVE | 0 | 35 | 26 | 0 | 0.195570707 | 0.311340183 | True |
| combined | with_news | INCERTITUDE_ELEVEE | 0 | 41 | 20 | 0 | 0.195570707 | 0.327981197 | True |
| combined | without_news | INFLATION_HAUTE | 0 | 23 | 38 | 0 | 0.195570707 | 0.317687521 | True |
| combined | without_news | INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.195570707 | 0.621997228 | False |
| combined | without_news | RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.195570707 | 0.416563850 | False |
| combined | without_news | RESSERREMENT | 0 | 16 | 45 | 0 | 0.195570707 | 0.350017392 | False |
| combined | without_news | ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.195570707 | 0.864599279 | False |
| combined | without_news | COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.195570707 | 0.320635961 | True |
| combined | without_news | STRESS_CREDIT | 0 | 0 | 61 | 0 | 0.195570707 | non estimable | False |
| combined | without_news | STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.195570707 | 0.483069895 | False |
| combined | without_news | CHOC_ENERGIE | 0 | 17 | 44 | 0 | 0.195570707 | 0.343403782 | False |
| combined | with_news | INFLATION_HAUTE | 1 | 23 | 38 | 0 | 0.201808694 | 0.327820587 | True |
| combined | with_news | INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.201808694 | 0.641836655 | False |
| combined | with_news | RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.201808694 | 0.448638257 | False |
| combined | with_news | RESSERREMENT | 1 | 17 | 44 | 0 | 0.201808694 | 0.354357101 | False |
| combined | with_news | ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.201808694 | 0.734712308 | False |
| combined | with_news | COURBE_INVERSEE | 1 | 22 | 39 | 0 | 0.201808694 | 0.330863070 | True |
| combined | with_news | STRESS_CREDIT | 1 | 0 | 61 | 0 | 0.201808694 | non estimable | False |
| combined | with_news | STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.201808694 | 0.413247842 | False |
| combined | with_news | CHOC_ENERGIE | 1 | 16 | 45 | 0 | 0.201808694 | 0.361181661 | False |
| combined | with_news | RISQUE_GEO_ELEVE | 1 | 37 | 24 | 0 | 0.201808694 | 0.325226149 | True |
| combined | with_news | INCERTITUDE_ELEVEE | 1 | 40 | 21 | 0 | 0.201808694 | 0.334389242 | True |
| combined | without_news | INFLATION_HAUTE | 1 | 23 | 38 | 0 | 0.201808694 | 0.327820587 | True |
| combined | without_news | INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.201808694 | 0.641836655 | False |
| combined | without_news | RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.201808694 | 0.448638257 | False |
| combined | without_news | RESSERREMENT | 1 | 17 | 44 | 0 | 0.201808694 | 0.354357101 | False |
| combined | without_news | ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.201808694 | 0.734712308 | False |
| combined | without_news | COURBE_INVERSEE | 1 | 22 | 39 | 0 | 0.201808694 | 0.330863070 | True |
| combined | without_news | STRESS_CREDIT | 1 | 0 | 61 | 0 | 0.201808694 | non estimable | False |
| combined | without_news | STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.201808694 | 0.413247842 | False |
| combined | without_news | CHOC_ENERGIE | 1 | 16 | 45 | 0 | 0.201808694 | 0.361181661 | False |
| combined | with_news | INFLATION_HAUTE | 2 | 24 | 37 | 0 | 0.201597486 | 0.324885774 | True |
| combined | with_news | INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.201597486 | 0.641164923 | False |
| combined | with_news | RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.201597486 | 0.448168721 | False |
| combined | with_news | RESSERREMENT | 2 | 18 | 43 | 0 | 0.201597486 | 0.347989947 | False |
| combined | with_news | ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | 0.201597486 | 0.641164923 | False |
| combined | with_news | COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.201597486 | 0.327477497 | True |
| combined | with_news | STRESS_CREDIT | 2 | 0 | 61 | 0 | 0.201597486 | non estimable | False |
| combined | with_news | STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.201597486 | 0.412815346 | False |
| combined | with_news | CHOC_ENERGIE | 2 | 18 | 43 | 0 | 0.201597486 | 0.347989947 | False |
| combined | with_news | RISQUE_GEO_ELEVE | 2 | 36 | 25 | 0 | 0.201597486 | 0.322712601 | True |
| combined | with_news | INCERTITUDE_ELEVEE | 2 | 41 | 20 | 0 | 0.201597486 | 0.338088386 | True |
| combined | without_news | INFLATION_HAUTE | 2 | 24 | 37 | 0 | 0.201597486 | 0.324885774 | True |
| combined | without_news | INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.201597486 | 0.641164923 | False |
| combined | without_news | RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.201597486 | 0.448168721 | False |
| combined | without_news | RESSERREMENT | 2 | 18 | 43 | 0 | 0.201597486 | 0.347989947 | False |
| combined | without_news | ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | 0.201597486 | 0.641164923 | False |
| combined | without_news | COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.201597486 | 0.327477497 | True |
| combined | without_news | STRESS_CREDIT | 2 | 0 | 61 | 0 | 0.201597486 | non estimable | False |
| combined | without_news | STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.201597486 | 0.412815346 | False |
| combined | without_news | CHOC_ENERGIE | 2 | 18 | 43 | 0 | 0.201597486 | 0.347989947 | False |
| combined | with_news | INFLATION_HAUTE | 3 | 24 | 37 | 0 | 0.177386468 | 0.285868347 | True |
| combined | with_news | INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.177386468 | 0.645799835 | False |
| combined | with_news | RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.177386468 | 0.363905718 | False |
| combined | with_news | RESSERREMENT | 3 | 18 | 43 | 0 | 0.177386468 | 0.306197805 | False |
| combined | with_news | ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | 0.177386468 | 0.645799835 | False |
| combined | with_news | COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.177386468 | 0.288148815 | True |
| combined | with_news | STRESS_CREDIT | 3 | 0 | 61 | 0 | 0.177386468 | non estimable | False |
| combined | with_news | STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.177386468 | 0.341020321 | False |
| combined | with_news | CHOC_ENERGIE | 3 | 18 | 43 | 0 | 0.177386468 | 0.306197805 | False |
| combined | with_news | RISQUE_GEO_ELEVE | 3 | 37 | 24 | 0 | 0.177386468 | 0.285868347 | True |
| combined | with_news | INCERTITUDE_ELEVEE | 3 | 39 | 22 | 0 | 0.177386468 | 0.290823107 | True |
| combined | without_news | INFLATION_HAUTE | 3 | 24 | 37 | 0 | 0.177386468 | 0.285868347 | True |
| combined | without_news | INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.177386468 | 0.645799835 | False |
| combined | without_news | RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.177386468 | 0.363905718 | False |
| combined | without_news | RESSERREMENT | 3 | 18 | 43 | 0 | 0.177386468 | 0.306197805 | False |
| combined | without_news | ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | 0.177386468 | 0.645799835 | False |
| combined | without_news | COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.177386468 | 0.288148815 | True |
| combined | without_news | STRESS_CREDIT | 3 | 0 | 61 | 0 | 0.177386468 | non estimable | False |
| combined | without_news | STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.177386468 | 0.341020321 | False |
| combined | without_news | CHOC_ENERGIE | 3 | 18 | 43 | 0 | 0.177386468 | 0.306197805 | False |
| combined | with_news | INFLATION_HAUTE | 4 | 24 | 36 | 0 | 0.161453384 | 0.261609226 | True |
| combined | with_news | INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.161453384 | 0.588046775 | False |
| combined | with_news | RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.161453384 | 0.358924897 | False |
| combined | with_news | RESSERREMENT | 4 | 16 | 44 | 0 | 0.161453384 | 0.289816827 | False |
| combined | with_news | ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | 0.161453384 | 0.713971593 | False |
| combined | with_news | COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.161453384 | 0.265954161 | True |
| combined | with_news | STRESS_CREDIT | 4 | 0 | 60 | 0 | 0.161453384 | non estimable | False |
| combined | with_news | STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.161453384 | 0.331219231 | False |
| combined | with_news | CHOC_ENERGIE | 4 | 18 | 42 | 0 | 0.161453384 | 0.279672027 | False |
| combined | with_news | RISQUE_GEO_ELEVE | 4 | 35 | 25 | 0 | 0.161453384 | 0.259959624 | True |
| combined | with_news | INCERTITUDE_ELEVEE | 4 | 38 | 22 | 0 | 0.161453384 | 0.265954161 | True |
| combined | without_news | INFLATION_HAUTE | 4 | 24 | 36 | 0 | 0.161453384 | 0.261609226 | True |
| combined | without_news | INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.161453384 | 0.588046775 | False |
| combined | without_news | RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.161453384 | 0.358924897 | False |
| combined | without_news | RESSERREMENT | 4 | 16 | 44 | 0 | 0.161453384 | 0.289816827 | False |
| combined | without_news | ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | 0.161453384 | 0.713971593 | False |
| combined | without_news | COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.161453384 | 0.265954161 | True |
| combined | without_news | STRESS_CREDIT | 4 | 0 | 60 | 0 | 0.161453384 | non estimable | False |
| combined | without_news | STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.161453384 | 0.331219231 | False |
| combined | without_news | CHOC_ENERGIE | 4 | 18 | 42 | 0 | 0.161453384 | 0.279672027 | False |

## 4. Bootstrap et intervalles — fixés avant calcul conditionnel

Un bloc élémentaire est un résultat à horizon cinq semaines non chevauchant dans son offset. Seuil de description : **au moins 20 blocs élémentaires connus dans chacun des groupes vrai ET faux**, dans chaque offset, pour permettre une interprétation de cet offset. Le non-chevauchement supprime le recouvrement mécanique des horizons ; il ne prouve pas l'indépendance économique des observations.

Bootstrap moving-block apparié, séparément par score/étiquette/offset : blocs contigus de **deux observations** (dix semaines), avec remise parmi les n−1 débuts possibles ; concaténation puis troncature à n dates. Les couples (IC, étiquette) sont rééchantillonnés ensemble et les dates manquantes restent à leur emplacement. Les groupes vrai/faux ne sont pas rééchantillonnés séparément. Les deux scores et les offsets ne sont pas réunis dans un échantillon artificiellement agrandi.

**100 000 réplications**, graine de base 20261018, sous-graine déterministe SHA256(score, étiquette, offset), aucune optimisation de longueur de bloc. Les réplications sans les deux groupes sont non estimables ; il faut au moins 99 % de réplications valides pour fournir l'intervalle. Intervalle bootstrap basic bilatéral aux quantiles α/(2×110) et 1−α/(2×110), soit **99,954545 % par contraste**, puis intersection avec les bornes physiques [−2,+2]. La couverture familiale de 95 % reste approximative car les intervalles bootstrap sont eux-mêmes estimés. Aucun changement de méthode selon le résultat.

## 5. Règles de conclusion fixées

Par offset : (1) moins de 20 blocs dans l'un des deux groupes, MDE ou intervalle non estimable : **données insuffisantes**, moyennes seulement décrites ; (2) sinon, intervalle corrigé excluant zéro : **effet détecté**, de signe donné par Δ ; (3) sinon, intervalle entièrement inclus strictement dans [−MDE,+MDE] : **absence d'effet détectable à l'échelle MDE** ; (4) autres cas : **données insuffisantes**. Un simple résultat non significatif n'est donc jamais une preuve d'absence. La MDE n'est pas un seuil qui annule une détection statistique ; le ratio |Δ|/MDE est rapporté séparément.

Conclusion d'ensemble par score/étiquette/ablation : les cinq offsets doivent satisfaire la condition d'effectifs et d'estimabilité. **Effet détecté** si au moins quatre offsets ont un effet détecté de même signe. **Absence d'effet détectable** si les cinq offsets satisfont la règle d'absence. Sinon **données insuffisantes**. Le nombre d'offsets de signe positif/négatif est rapporté, sans les traiter comme cinq études indépendantes. Aucun agrégat d'effectif ni p-value pooled entre offsets.

Le rapport donne chaque offset : n vrai/faux/NA, IC moyens vrai/faux, Δ, intervalle corrigé, MDE, |Δ|/MDE et verdict ; puis la cohérence des cinq offsets. Les cas rares ne sont jamais interprétés, même si une moyenne ou un intervalle paraît favorable.

## 6. Verrouillage et reproductibilité

Ordre obligatoire : préparer et vérifier les scores ; calculer uniquement les comptages/σ/MDE ; committer ce protocole, les données de puissance et le code ; créer le tag annoté protocol-ic-v1.0 ; pousser branche et tag ; vérifier le tag distant ; ensuite seulement exécuter infer.py. Le programme d'inférence vérifie l'existence du tag, son ascendance, l'identité des fichiers de protocole/code et les empreintes des entrées, avant toute partition numérique de l'IC. Les tests antérieurs au tag utilisent exclusivement des données synthétiques.

Les sorties de calcul, prédictions par titre, cibles, jointures et tirages bootstrap restent hors Git. Les documents ne contiennent que paramètres, empreintes, effectifs et résultats agrégés. Aucun fichier src/, règle de portefeuille, réglage de modèle ou ordres n'est modifié. La PR du moteur macro reste sur feature/macro-engine ; cette recherche demeure sur research/macro-conditional-ic.

Références méthodologiques primaires : [NIST, puissance et taille d'échantillon](https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm) ; [NIST, différence de moyennes](https://www.itl.nist.gov/div898/handbook/prc/section3/prc312.htm) ; [NIST, Bonferroni](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm) ; [Künsch (1989), bootstrap de séries stationnaires](https://doi.org/10.1214/aos/1176347265) ; [SciPy, types d'intervalles bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). Le facteur d'inflation 2 et les règles de conclusion sont les choix de ce protocole, pas des garanties fournies par ces références.
