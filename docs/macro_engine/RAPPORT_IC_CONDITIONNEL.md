# Rapport — test de passage IC conditionnel

Date : 18 octobre 2026. Branche : research/macro-conditional-ic. PR du moteur macro : [n°9](https://github.com/thomasdgn/bloomberg-trading-challenge-quant-lab/pull/9), ouverte sans fusion. Protocole : [PROTOCOLE_IC_CONDITIONNEL.md](PROTOCOLE_IC_CONDITIONNEL.md), tag **protocol-ic-v1.0**, commit **fc3d450069263907126eddb9ee75459f2fda8902**.

## 1. Résultat selon le protocole

La conclusion ci-dessous suit exclusivement les critères figés : 20 blocs cinq semaines au minimum dans chacun des groupes et chacun des cinq offsets ; intervalle bootstrap corrigé Bonferroni ; cohérence entre offsets. Un faible effectif est décrit mais jamais interprété. « Absence » signifie uniquement absence d'effet détectable à l'échelle MDE préenregistrée, pas preuve d'un effet exactement nul.

| Conclusion d'ensemble | Nombre de lignes score × ablation × étiquette |
| --- | --- |
| donnees_insuffisantes | 28 |
| absence_effet_detectable | 12 |
| effet_detecte | 0 |

Les étiquettes communes aux deux ablations sont des répétitions des mêmes contrastes. Les nombres de lignes ne constituent pas autant d'expériences indépendantes ; les offsets se recouvrent entre eux. Aucune comparaison de rendements ni règle de portefeuille n'est déduite de ce test.

Après déduplication des étiquettes communes aux ablations : **22 couples score–étiquette uniques**, dont **8 absences d'effet détectable, 14 données insuffisantes et aucun effet détecté**. Les huit cas estimables correspondent à INFLATION_HAUTE, COURBE_INVERSEE, RISQUE_GEO_ELEVE et INCERTITUDE_ELEVEE pour chacun des deux scores. Pour les deux premières étiquettes, le résultat est identique avec et sans GPR/EPU ; les deux dernières existent seulement avec GPR/EPU.

La résolution est limitée : pour ces huit cas, les MDE vont approximativement de **0,242 à 0,338 point d'IC** selon le score et l'offset. L'absence conclue par la règle préenregistrée concerne cette échelle ; elle n'exclut pas des associations plus petites. Les sept autres étiquettes par score restent descriptives faute d'au moins 20 blocs dans chacun des groupes. Aucun sens économique n'est attribué à leurs signes.

## 2. Données et traçabilité

Source utilisée après autorisation explicite : scores cinq semaines régénérés avec le code figé de quant-lab, sans modification du cœur. Panel sauvegardé et cible future_excess_return_5w lus directement ; le module macro n'a jamais recalculé de rendement futur. Les anciens fichiers par titre n'offraient pas les deux scores sur les cinq offsets.

349983 prédictions titre-date ; 608 IC par date/score ; cinq offsets couvrant les 304 dates du 06/11/2020 au 28/08/2026. Les deux scores ont été évalués sur les mêmes titres complets. La régénération garde les paramètres historiques et le mélange de rangs 75 % Tail / 25 % Elastic Net.

Recalcul de tous les Spearman à partir des scores par titre après le tag : différence maximale avec la table inconditionnelle de préparation **0**. Jointure réelle aux étiquettes : 699966 lignes titre-date-ablation ; zéro violation de prediction_date > macro_date. La date macro est la dernière séance strictement antérieure ; aucune étiquette NA n'est remplacée par sa valeur passée.

Réconciliation globale de préparation avec les archives V1, sans condition macro : {"saved_prediction_pairs": 70232, "max_abs_prediction_difference": 9.999054535747565e-17, "saved_ic_pairs": 304, "max_abs_ic_difference": 9.71445146547012e-17}. Les hashes des données régénérées, du panel, des étiquettes et du tableau MDE sont figés dans INPUTS_IC_CONDITIONNEL.json. Les sorties détaillées restent sous `C:\Users\degar\.codex\visualizations\2026\10\16\01a1452a-73d3-7e00-b07a-3a2d4fa52c4c\quant-lab-macro\outputs\macro_conditional_ic\results` et ne sont pas committées.

## 3. Comparaison par étiquette et cohérence des offsets

Effectifs ci-dessous : minimum parmi les cinq offsets, jamais somme de dates chevauchantes. Les colonnes +/− donnent le nombre de différences de signe positif/négatif, à titre descriptif si les effectifs sont insuffisants.

| Score | Ablation | Étiquette | min vrai | min faux | Offsets estimables /5 | + / − | MDE min–max | Conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| elastic_net | with_news | INFLATION_HAUTE | 23 | 36 | 5/5 | 0 / 5 | 0.2432–0.2983 | absence_effet_detectable |
| elastic_net | with_news | INFLATION_BASSE | 3 | 57 | 0/5 | 5 / 0 | 0.5466–0.6155 | donnees_insuffisantes |
| elastic_net | with_news | RALENTISSEMENT | 9 | 49 | 0/5 | 5 / 0 | 0.3336–0.4092 | donnees_insuffisantes |
| elastic_net | with_news | RESSERREMENT | 16 | 43 | 0/5 | 1 / 4 | 0.2694–0.3225 | donnees_insuffisantes |
| elastic_net | with_news | ASSOUPLISSEMENT | 2 | 57 | 0/5 | 2 / 3 | 0.5854–0.7793 | donnees_insuffisantes |
| elastic_net | with_news | COURBE_INVERSEE | 22 | 38 | 5/5 | 2 / 3 | 0.2472–0.3011 | absence_effet_detectable |
| elastic_net | with_news | STRESS_CREDIT | 0 | 60 | 0/5 | 0 / 0 | non estimable | donnees_insuffisantes |
| elastic_net | with_news | STRESS_MARCHE | 7 | 48 | 0/5 | 5 / 0 | 0.3079–0.4354 | donnees_insuffisantes |
| elastic_net | with_news | CHOC_ENERGIE | 16 | 42 | 0/5 | 0 / 5 | 0.2600–0.3287 | donnees_insuffisantes |
| elastic_net | with_news | RISQUE_GEO_ELEVE | 35 | 24 | 5/5 | 5 / 0 | 0.2416–0.2960 | absence_effet_detectable |
| elastic_net | with_news | INCERTITUDE_ELEVEE | 38 | 20 | 5/5 | 5 / 0 | 0.2472–0.3087 | absence_effet_detectable |
| elastic_net | without_news | INFLATION_HAUTE | 23 | 36 | 5/5 | 0 / 5 | 0.2432–0.2983 | absence_effet_detectable |
| elastic_net | without_news | INFLATION_BASSE | 3 | 57 | 0/5 | 5 / 0 | 0.5466–0.6155 | donnees_insuffisantes |
| elastic_net | without_news | RALENTISSEMENT | 9 | 49 | 0/5 | 5 / 0 | 0.3336–0.4092 | donnees_insuffisantes |
| elastic_net | without_news | RESSERREMENT | 16 | 43 | 0/5 | 1 / 4 | 0.2694–0.3225 | donnees_insuffisantes |
| elastic_net | without_news | ASSOUPLISSEMENT | 2 | 57 | 0/5 | 2 / 3 | 0.5854–0.7793 | donnees_insuffisantes |
| elastic_net | without_news | COURBE_INVERSEE | 22 | 38 | 5/5 | 2 / 3 | 0.2472–0.3011 | absence_effet_detectable |
| elastic_net | without_news | STRESS_CREDIT | 0 | 60 | 0/5 | 0 / 0 | non estimable | donnees_insuffisantes |
| elastic_net | without_news | STRESS_MARCHE | 7 | 48 | 0/5 | 5 / 0 | 0.3079–0.4354 | donnees_insuffisantes |
| elastic_net | without_news | CHOC_ENERGIE | 16 | 42 | 0/5 | 0 / 5 | 0.2600–0.3287 | donnees_insuffisantes |
| combined | with_news | INFLATION_HAUTE | 23 | 36 | 5/5 | 0 / 5 | 0.2616–0.3278 | absence_effet_detectable |
| combined | with_news | INFLATION_BASSE | 3 | 57 | 0/5 | 5 / 0 | 0.5880–0.6458 | donnees_insuffisantes |
| combined | with_news | RALENTISSEMENT | 9 | 49 | 0/5 | 5 / 0 | 0.3589–0.4486 | donnees_insuffisantes |
| combined | with_news | RESSERREMENT | 16 | 43 | 0/5 | 0 / 5 | 0.2898–0.3544 | donnees_insuffisantes |
| combined | with_news | ASSOUPLISSEMENT | 2 | 57 | 0/5 | 3 / 2 | 0.6412–0.8646 | donnees_insuffisantes |
| combined | with_news | COURBE_INVERSEE | 22 | 38 | 5/5 | 2 / 3 | 0.2660–0.3309 | absence_effet_detectable |
| combined | with_news | STRESS_CREDIT | 0 | 60 | 0/5 | 0 / 0 | non estimable | donnees_insuffisantes |
| combined | with_news | STRESS_MARCHE | 7 | 48 | 0/5 | 5 / 0 | 0.3312–0.4831 | donnees_insuffisantes |
| combined | with_news | CHOC_ENERGIE | 16 | 42 | 0/5 | 0 / 5 | 0.2797–0.3612 | donnees_insuffisantes |
| combined | with_news | RISQUE_GEO_ELEVE | 35 | 24 | 5/5 | 5 / 0 | 0.2600–0.3252 | absence_effet_detectable |
| combined | with_news | INCERTITUDE_ELEVEE | 38 | 20 | 5/5 | 5 / 0 | 0.2660–0.3381 | absence_effet_detectable |
| combined | without_news | INFLATION_HAUTE | 23 | 36 | 5/5 | 0 / 5 | 0.2616–0.3278 | absence_effet_detectable |
| combined | without_news | INFLATION_BASSE | 3 | 57 | 0/5 | 5 / 0 | 0.5880–0.6458 | donnees_insuffisantes |
| combined | without_news | RALENTISSEMENT | 9 | 49 | 0/5 | 5 / 0 | 0.3589–0.4486 | donnees_insuffisantes |
| combined | without_news | RESSERREMENT | 16 | 43 | 0/5 | 0 / 5 | 0.2898–0.3544 | donnees_insuffisantes |
| combined | without_news | ASSOUPLISSEMENT | 2 | 57 | 0/5 | 3 / 2 | 0.6412–0.8646 | donnees_insuffisantes |
| combined | without_news | COURBE_INVERSEE | 22 | 38 | 5/5 | 2 / 3 | 0.2660–0.3309 | absence_effet_detectable |
| combined | without_news | STRESS_CREDIT | 0 | 60 | 0/5 | 0 / 0 | non estimable | donnees_insuffisantes |
| combined | without_news | STRESS_MARCHE | 7 | 48 | 0/5 | 5 / 0 | 0.3312–0.4831 | donnees_insuffisantes |
| combined | without_news | CHOC_ENERGIE | 16 | 42 | 0/5 | 0 / 5 | 0.2797–0.3612 | donnees_insuffisantes |

## 4. Tous les résultats par offset

IC moyen vrai/faux, écart et MDE en points d'IC. Intervalle basic moving-block à **99,954545 %**, correction de la famille de 110 contrastes uniques ; 100 000 réplications, blocs de dix semaines. Les effectifs sont des horizons élémentaires de cinq semaines non chevauchants. Les valeurs des lignes sous le seuil de 20 ne sont que descriptives.

### elastic_net — with_news

| Étiquette | Offset | n vrai | n faux | NA | IC vrai | IC faux | Écart | IC bas | IC haut | MDE | Δ absolu / MDE | Conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INFLATION_HAUTE | 0 | 23 | 38 | 0 | -0.014041 | 0.056646 | -0.070687 | -0.207715 | 0.067752 | 0.286352 | 0.246854 | absence_effet_detectable |
| INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.091455 | 0.025681 | 0.065774 | non estimable | non estimable | 0.560645 | 0.117319 | donnees_insuffisantes |
| RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.099086 | 0.015862 | 0.083224 | -0.184646 | 0.330165 | 0.375475 | 0.221651 | donnees_insuffisantes |
| RESSERREMENT | 0 | 16 | 45 | 0 | 0.021807 | 0.032905 | -0.011097 | -0.158166 | 0.143254 | 0.315492 | 0.035175 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.101455 | 0.027571 | 0.073883 | non estimable | non estimable | 0.779317 | 0.094805 | donnees_insuffisantes |
| COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.011449 | 0.040455 | -0.029006 | -0.184040 | 0.119614 | 0.289009 | 0.100362 | absence_effet_detectable |
| STRESS_CREDIT | 0 | 0 | 61 | 0 | non estimable | 0.029994 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.112390 | 0.019313 | 0.093078 | -0.170710 | 0.388995 | 0.435421 | 0.213765 | donnees_insuffisantes |
| CHOC_ENERGIE | 0 | 17 | 44 | 0 | -0.021822 | 0.050014 | -0.071836 | -0.217823 | 0.071753 | 0.309531 | 0.232080 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 0 | 35 | 26 | 0 | 0.049978 | 0.003093 | 0.046885 | -0.128010 | 0.210621 | 0.280630 | 0.167070 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 0 | 41 | 20 | 0 | 0.051538 | -0.014171 | 0.065708 | -0.078368 | 0.214724 | 0.295630 | 0.222265 | absence_effet_detectable |
| INFLATION_HAUTE | 1 | 23 | 38 | 0 | -0.020240 | 0.037360 | -0.057601 | -0.218394 | 0.105093 | 0.298340 | 0.193070 | absence_effet_detectable |
| INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.079550 | 0.011157 | 0.068394 | non estimable | non estimable | 0.584117 | 0.117089 | donnees_insuffisantes |
| RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.055045 | 0.010361 | 0.044684 | -0.114154 | 0.257491 | 0.408292 | 0.109441 | donnees_insuffisantes |
| RESSERREMENT | 1 | 17 | 44 | 0 | -0.009418 | 0.025324 | -0.034742 | -0.204662 | 0.144437 | 0.322490 | 0.107729 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.108858 | 0.010820 | 0.098037 | non estimable | non estimable | 0.668640 | 0.146622 | donnees_insuffisantes |
| COURBE_INVERSEE | 1 | 22 | 39 | 0 | -0.005686 | 0.027673 | -0.033359 | -0.186840 | 0.119312 | 0.301109 | 0.110787 | absence_effet_detectable |
| STRESS_CREDIT | 1 | 0 | 61 | 0 | non estimable | 0.015642 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.087272 | -0.000117 | 0.087388 | -0.327779 | 0.469883 | 0.376085 | 0.232363 | donnees_insuffisantes |
| CHOC_ENERGIE | 1 | 16 | 45 | 0 | -0.034368 | 0.033423 | -0.067791 | -0.274842 | 0.092057 | 0.328701 | 0.206238 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 1 | 37 | 24 | 0 | 0.033010 | -0.011134 | 0.044143 | -0.126040 | 0.197611 | 0.295979 | 0.149143 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 1 | 40 | 21 | 0 | 0.043726 | -0.037852 | 0.081578 | -0.051129 | 0.210158 | 0.304318 | 0.268068 | absence_effet_detectable |
| INFLATION_HAUTE | 2 | 24 | 37 | 0 | -0.016707 | 0.049366 | -0.066073 | -0.223843 | 0.090830 | 0.296608 | 0.222760 | absence_effet_detectable |
| INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.111086 | 0.017214 | 0.093872 | non estimable | non estimable | 0.585359 | 0.160366 | donnees_insuffisantes |
| RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.070114 | 0.016798 | 0.053315 | -0.233192 | 0.278723 | 0.409161 | 0.130304 | donnees_insuffisantes |
| RESSERREMENT | 2 | 18 | 43 | 0 | 0.015042 | 0.026856 | -0.011813 | -0.185232 | 0.160861 | 0.317701 | 0.037184 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | -0.026586 | 0.026875 | -0.053461 | non estimable | non estimable | 0.585359 | 0.091331 | donnees_insuffisantes |
| COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.014046 | 0.029013 | -0.014967 | -0.178641 | 0.136519 | 0.298974 | 0.050061 | absence_effet_detectable |
| STRESS_CREDIT | 2 | 0 | 61 | 0 | non estimable | 0.023370 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.082701 | 0.010317 | 0.072384 | -0.336563 | 0.369331 | 0.376884 | 0.192058 | donnees_insuffisantes |
| CHOC_ENERGIE | 2 | 18 | 43 | 0 | -0.018175 | 0.040761 | -0.058936 | -0.256316 | 0.116240 | 0.317701 | 0.185508 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 2 | 36 | 25 | 0 | 0.031294 | 0.011959 | 0.019334 | -0.151807 | 0.171128 | 0.294624 | 0.065623 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 2 | 41 | 20 | 0 | 0.044601 | -0.020155 | 0.064756 | -0.090887 | 0.231286 | 0.308662 | 0.209797 | absence_effet_detectable |
| INFLATION_HAUTE | 3 | 24 | 37 | 0 | -0.011036 | 0.049281 | -0.060317 | -0.210775 | 0.087113 | 0.272477 | 0.221365 | absence_effet_detectable |
| INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.207426 | 0.016142 | 0.191284 | non estimable | non estimable | 0.615548 | 0.310754 | donnees_insuffisantes |
| RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.074953 | 0.013547 | 0.061406 | -0.170549 | 0.253672 | 0.346859 | 0.177034 | donnees_insuffisantes |
| RESSERREMENT | 3 | 18 | 43 | 0 | 0.012018 | 0.031214 | -0.019196 | -0.180600 | 0.155914 | 0.291854 | 0.065771 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | -0.097630 | 0.031921 | -0.129551 | non estimable | non estimable | 0.615548 | 0.210465 | donnees_insuffisantes |
| COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.028629 | 0.023686 | 0.004943 | -0.135537 | 0.141429 | 0.274651 | 0.017999 | absence_effet_detectable |
| STRESS_CREDIT | 3 | 0 | 61 | 0 | non estimable | 0.025550 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.055193 | 0.017521 | 0.037672 | -0.153588 | 0.236209 | 0.325046 | 0.115898 | donnees_insuffisantes |
| CHOC_ENERGIE | 3 | 18 | 43 | 0 | -0.023841 | 0.046225 | -0.070066 | -0.249246 | 0.097766 | 0.291854 | 0.240072 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 3 | 37 | 24 | 0 | 0.038530 | 0.005539 | 0.032991 | -0.112468 | 0.173452 | 0.272477 | 0.121078 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 3 | 39 | 22 | 0 | 0.045152 | -0.009200 | 0.054353 | -0.091000 | 0.228906 | 0.277200 | 0.196078 | absence_effet_detectable |
| INFLATION_HAUTE | 4 | 24 | 36 | 0 | -0.001710 | 0.037571 | -0.039280 | -0.192980 | 0.112075 | 0.243183 | 0.161527 | absence_effet_detectable |
| INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.114984 | 0.016957 | 0.098027 | non estimable | non estimable | 0.546628 | 0.179331 | donnees_insuffisantes |
| RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.066504 | 0.013980 | 0.052524 | -0.161932 | 0.213855 | 0.333644 | 0.157425 | donnees_insuffisantes |
| RESSERREMENT | 4 | 16 | 44 | 0 | 0.026804 | 0.020060 | 0.006744 | -0.163825 | 0.174905 | 0.269404 | 0.025035 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | -0.024375 | 0.023453 | -0.047828 | non estimable | non estimable | 0.663683 | 0.072064 | donnees_insuffisantes |
| COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.022873 | 0.021271 | 0.001603 | -0.150541 | 0.138554 | 0.247222 | 0.006482 | absence_effet_detectable |
| STRESS_CREDIT | 4 | 0 | 60 | 0 | non estimable | 0.021858 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.082298 | 0.008290 | 0.074008 | -0.100139 | 0.392116 | 0.307890 | 0.240372 | donnees_insuffisantes |
| CHOC_ENERGIE | 4 | 18 | 42 | 0 | -0.017116 | 0.038562 | -0.055678 | -0.217052 | 0.108734 | 0.259973 | 0.214167 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 4 | 35 | 25 | 0 | 0.043544 | -0.008502 | 0.052046 | -0.099548 | 0.182178 | 0.241649 | 0.215379 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 4 | 38 | 22 | 0 | 0.040681 | -0.010653 | 0.051333 | -0.074997 | 0.190292 | 0.247222 | 0.207640 | absence_effet_detectable |

### elastic_net — without_news

| Étiquette | Offset | n vrai | n faux | NA | IC vrai | IC faux | Écart | IC bas | IC haut | MDE | Δ absolu / MDE | Conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INFLATION_HAUTE | 0 | 23 | 38 | 0 | -0.014041 | 0.056646 | -0.070687 | -0.207715 | 0.067752 | 0.286352 | 0.246854 | absence_effet_detectable |
| INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.091455 | 0.025681 | 0.065774 | non estimable | non estimable | 0.560645 | 0.117319 | donnees_insuffisantes |
| RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.099086 | 0.015862 | 0.083224 | -0.184646 | 0.330165 | 0.375475 | 0.221651 | donnees_insuffisantes |
| RESSERREMENT | 0 | 16 | 45 | 0 | 0.021807 | 0.032905 | -0.011097 | -0.158166 | 0.143254 | 0.315492 | 0.035175 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.101455 | 0.027571 | 0.073883 | non estimable | non estimable | 0.779317 | 0.094805 | donnees_insuffisantes |
| COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.011449 | 0.040455 | -0.029006 | -0.184040 | 0.119614 | 0.289009 | 0.100362 | absence_effet_detectable |
| STRESS_CREDIT | 0 | 0 | 61 | 0 | non estimable | 0.029994 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.112390 | 0.019313 | 0.093078 | -0.170710 | 0.388995 | 0.435421 | 0.213765 | donnees_insuffisantes |
| CHOC_ENERGIE | 0 | 17 | 44 | 0 | -0.021822 | 0.050014 | -0.071836 | -0.217823 | 0.071753 | 0.309531 | 0.232080 | donnees_insuffisantes |
| INFLATION_HAUTE | 1 | 23 | 38 | 0 | -0.020240 | 0.037360 | -0.057601 | -0.218394 | 0.105093 | 0.298340 | 0.193070 | absence_effet_detectable |
| INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.079550 | 0.011157 | 0.068394 | non estimable | non estimable | 0.584117 | 0.117089 | donnees_insuffisantes |
| RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.055045 | 0.010361 | 0.044684 | -0.114154 | 0.257491 | 0.408292 | 0.109441 | donnees_insuffisantes |
| RESSERREMENT | 1 | 17 | 44 | 0 | -0.009418 | 0.025324 | -0.034742 | -0.204662 | 0.144437 | 0.322490 | 0.107729 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.108858 | 0.010820 | 0.098037 | non estimable | non estimable | 0.668640 | 0.146622 | donnees_insuffisantes |
| COURBE_INVERSEE | 1 | 22 | 39 | 0 | -0.005686 | 0.027673 | -0.033359 | -0.186840 | 0.119312 | 0.301109 | 0.110787 | absence_effet_detectable |
| STRESS_CREDIT | 1 | 0 | 61 | 0 | non estimable | 0.015642 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.087272 | -0.000117 | 0.087388 | -0.327779 | 0.469883 | 0.376085 | 0.232363 | donnees_insuffisantes |
| CHOC_ENERGIE | 1 | 16 | 45 | 0 | -0.034368 | 0.033423 | -0.067791 | -0.274842 | 0.092057 | 0.328701 | 0.206238 | donnees_insuffisantes |
| INFLATION_HAUTE | 2 | 24 | 37 | 0 | -0.016707 | 0.049366 | -0.066073 | -0.223843 | 0.090830 | 0.296608 | 0.222760 | absence_effet_detectable |
| INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.111086 | 0.017214 | 0.093872 | non estimable | non estimable | 0.585359 | 0.160366 | donnees_insuffisantes |
| RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.070114 | 0.016798 | 0.053315 | -0.233192 | 0.278723 | 0.409161 | 0.130304 | donnees_insuffisantes |
| RESSERREMENT | 2 | 18 | 43 | 0 | 0.015042 | 0.026856 | -0.011813 | -0.185232 | 0.160861 | 0.317701 | 0.037184 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | -0.026586 | 0.026875 | -0.053461 | non estimable | non estimable | 0.585359 | 0.091331 | donnees_insuffisantes |
| COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.014046 | 0.029013 | -0.014967 | -0.178641 | 0.136519 | 0.298974 | 0.050061 | absence_effet_detectable |
| STRESS_CREDIT | 2 | 0 | 61 | 0 | non estimable | 0.023370 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.082701 | 0.010317 | 0.072384 | -0.336563 | 0.369331 | 0.376884 | 0.192058 | donnees_insuffisantes |
| CHOC_ENERGIE | 2 | 18 | 43 | 0 | -0.018175 | 0.040761 | -0.058936 | -0.256316 | 0.116240 | 0.317701 | 0.185508 | donnees_insuffisantes |
| INFLATION_HAUTE | 3 | 24 | 37 | 0 | -0.011036 | 0.049281 | -0.060317 | -0.210775 | 0.087113 | 0.272477 | 0.221365 | absence_effet_detectable |
| INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.207426 | 0.016142 | 0.191284 | non estimable | non estimable | 0.615548 | 0.310754 | donnees_insuffisantes |
| RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.074953 | 0.013547 | 0.061406 | -0.170549 | 0.253672 | 0.346859 | 0.177034 | donnees_insuffisantes |
| RESSERREMENT | 3 | 18 | 43 | 0 | 0.012018 | 0.031214 | -0.019196 | -0.180600 | 0.155914 | 0.291854 | 0.065771 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | -0.097630 | 0.031921 | -0.129551 | non estimable | non estimable | 0.615548 | 0.210465 | donnees_insuffisantes |
| COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.028629 | 0.023686 | 0.004943 | -0.135537 | 0.141429 | 0.274651 | 0.017999 | absence_effet_detectable |
| STRESS_CREDIT | 3 | 0 | 61 | 0 | non estimable | 0.025550 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.055193 | 0.017521 | 0.037672 | -0.153588 | 0.236209 | 0.325046 | 0.115898 | donnees_insuffisantes |
| CHOC_ENERGIE | 3 | 18 | 43 | 0 | -0.023841 | 0.046225 | -0.070066 | -0.249246 | 0.097766 | 0.291854 | 0.240072 | donnees_insuffisantes |
| INFLATION_HAUTE | 4 | 24 | 36 | 0 | -0.001710 | 0.037571 | -0.039280 | -0.192980 | 0.112075 | 0.243183 | 0.161527 | absence_effet_detectable |
| INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.114984 | 0.016957 | 0.098027 | non estimable | non estimable | 0.546628 | 0.179331 | donnees_insuffisantes |
| RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.066504 | 0.013980 | 0.052524 | -0.161932 | 0.213855 | 0.333644 | 0.157425 | donnees_insuffisantes |
| RESSERREMENT | 4 | 16 | 44 | 0 | 0.026804 | 0.020060 | 0.006744 | -0.163825 | 0.174905 | 0.269404 | 0.025035 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | -0.024375 | 0.023453 | -0.047828 | non estimable | non estimable | 0.663683 | 0.072064 | donnees_insuffisantes |
| COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.022873 | 0.021271 | 0.001603 | -0.150541 | 0.138554 | 0.247222 | 0.006482 | absence_effet_detectable |
| STRESS_CREDIT | 4 | 0 | 60 | 0 | non estimable | 0.021858 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.082298 | 0.008290 | 0.074008 | -0.100139 | 0.392116 | 0.307890 | 0.240372 | donnees_insuffisantes |
| CHOC_ENERGIE | 4 | 18 | 42 | 0 | -0.017116 | 0.038562 | -0.055678 | -0.217052 | 0.108734 | 0.259973 | 0.214167 | donnees_insuffisantes |

### combined — with_news

| Étiquette | Offset | n vrai | n faux | NA | IC vrai | IC faux | Écart | IC bas | IC haut | MDE | Δ absolu / MDE | Conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INFLATION_HAUTE | 0 | 23 | 38 | 0 | -0.009629 | 0.065150 | -0.074779 | -0.250454 | 0.078392 | 0.317688 | 0.235384 | absence_effet_detectable |
| INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.141109 | 0.029645 | 0.111464 | non estimable | non estimable | 0.621997 | 0.179203 | donnees_insuffisantes |
| RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.088627 | 0.026699 | 0.061928 | -0.240868 | 0.340567 | 0.416564 | 0.148665 | donnees_insuffisantes |
| RESSERREMENT | 0 | 16 | 45 | 0 | 0.013035 | 0.045459 | -0.032424 | -0.195646 | 0.127833 | 0.350017 | 0.092635 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.160908 | 0.032753 | 0.128155 | non estimable | non estimable | 0.864599 | 0.148225 | donnees_insuffisantes |
| COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.008201 | 0.053174 | -0.044973 | -0.223641 | 0.125700 | 0.320636 | 0.140262 | absence_effet_detectable |
| STRESS_CREDIT | 0 | 0 | 61 | 0 | non estimable | 0.036954 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.129208 | 0.024996 | 0.104212 | -0.209829 | 0.496381 | 0.483070 | 0.215729 | donnees_insuffisantes |
| CHOC_ENERGIE | 0 | 17 | 44 | 0 | -0.032996 | 0.063981 | -0.096977 | -0.252556 | 0.050886 | 0.343404 | 0.282398 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 0 | 35 | 26 | 0 | 0.053662 | 0.014463 | 0.039199 | -0.155474 | 0.219397 | 0.311340 | 0.125903 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 0 | 41 | 20 | 0 | 0.063912 | -0.018310 | 0.082222 | -0.078316 | 0.242749 | 0.327981 | 0.250692 | absence_effet_detectable |
| INFLATION_HAUTE | 1 | 23 | 38 | 0 | -0.019771 | 0.053122 | -0.072894 | -0.260555 | 0.098874 | 0.327821 | 0.222358 | absence_effet_detectable |
| INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.126511 | 0.018559 | 0.107951 | non estimable | non estimable | 0.641837 | 0.168191 | donnees_insuffisantes |
| RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.088236 | 0.016913 | 0.071322 | -0.105756 | 0.305356 | 0.448638 | 0.158975 | donnees_insuffisantes |
| RESSERREMENT | 1 | 17 | 44 | 0 | -0.015304 | 0.041456 | -0.056760 | -0.251401 | 0.131138 | 0.354357 | 0.160177 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.199656 | 0.016637 | 0.183019 | non estimable | non estimable | 0.734712 | 0.249103 | donnees_insuffisantes |
| COURBE_INVERSEE | 1 | 22 | 39 | 0 | 0.006082 | 0.036670 | -0.030588 | -0.206851 | 0.140026 | 0.330863 | 0.092450 | absence_effet_detectable |
| STRESS_CREDIT | 1 | 0 | 61 | 0 | non estimable | 0.025638 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.099472 | 0.009395 | 0.090077 | -0.346460 | 0.512665 | 0.413248 | 0.217973 | donnees_insuffisantes |
| CHOC_ENERGIE | 1 | 16 | 45 | 0 | -0.043829 | 0.050337 | -0.094166 | -0.303457 | 0.065997 | 0.361182 | 0.260716 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 1 | 37 | 24 | 0 | 0.040139 | 0.003283 | 0.036856 | -0.151356 | 0.204723 | 0.325226 | 0.113323 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 1 | 40 | 21 | 0 | 0.054725 | -0.029766 | 0.084490 | -0.070685 | 0.233010 | 0.334389 | 0.252671 | absence_effet_detectable |
| INFLATION_HAUTE | 2 | 24 | 37 | 0 | -0.013189 | 0.056436 | -0.069626 | -0.253598 | 0.101151 | 0.324886 | 0.214308 | absence_effet_detectable |
| INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.128133 | 0.022089 | 0.106044 | non estimable | non estimable | 0.641165 | 0.165392 | donnees_insuffisantes |
| RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.103208 | 0.017899 | 0.085309 | -0.234608 | 0.348780 | 0.448169 | 0.190350 | donnees_insuffisantes |
| RESSERREMENT | 2 | 18 | 43 | 0 | 0.010597 | 0.036764 | -0.026167 | -0.226398 | 0.165283 | 0.347990 | 0.075196 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | 0.012496 | 0.030204 | -0.017708 | non estimable | non estimable | 0.641165 | 0.027619 | donnees_insuffisantes |
| COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.017645 | 0.035941 | -0.018297 | -0.203151 | 0.155159 | 0.327477 | 0.055871 | absence_effet_detectable |
| STRESS_CREDIT | 2 | 0 | 61 | 0 | non estimable | 0.029043 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.090118 | 0.015606 | 0.074512 | -0.330610 | 0.400983 | 0.412815 | 0.180497 | donnees_insuffisantes |
| CHOC_ENERGIE | 2 | 18 | 43 | 0 | -0.022451 | 0.050598 | -0.073050 | -0.297711 | 0.109043 | 0.347990 | 0.209918 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 2 | 36 | 25 | 0 | 0.041294 | 0.011401 | 0.029894 | -0.171136 | 0.208350 | 0.322713 | 0.092632 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 2 | 41 | 20 | 0 | 0.052192 | -0.018414 | 0.070606 | -0.112016 | 0.243226 | 0.338088 | 0.208838 | absence_effet_detectable |
| INFLATION_HAUTE | 3 | 24 | 37 | 0 | -0.006120 | 0.052218 | -0.058338 | -0.225377 | 0.105368 | 0.285868 | 0.204073 | absence_effet_detectable |
| INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.193079 | 0.020792 | 0.172288 | non estimable | non estimable | 0.645800 | 0.266782 | donnees_insuffisantes |
| RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.100671 | 0.012843 | 0.087828 | -0.187838 | 0.281081 | 0.363906 | 0.241349 | donnees_insuffisantes |
| RESSERREMENT | 3 | 18 | 43 | 0 | 0.017924 | 0.034012 | -0.016088 | -0.199381 | 0.179288 | 0.306198 | 0.052541 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | -0.013237 | 0.031463 | -0.044700 | non estimable | non estimable | 0.645800 | 0.069217 | donnees_insuffisantes |
| COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.029734 | 0.028981 | 0.000752 | -0.153496 | 0.150320 | 0.288149 | 0.002611 | absence_effet_detectable |
| STRESS_CREDIT | 3 | 0 | 61 | 0 | non estimable | 0.029265 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.046468 | 0.024606 | 0.021862 | -0.183433 | 0.217440 | 0.341020 | 0.064107 | donnees_insuffisantes |
| CHOC_ENERGIE | 3 | 18 | 43 | 0 | -0.028790 | 0.053567 | -0.082357 | -0.263327 | 0.086522 | 0.306198 | 0.268967 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 3 | 37 | 24 | 0 | 0.046562 | 0.002599 | 0.043963 | -0.114310 | 0.192971 | 0.285868 | 0.153787 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 3 | 39 | 22 | 0 | 0.051705 | -0.010515 | 0.062220 | -0.093701 | 0.240606 | 0.290823 | 0.213945 | absence_effet_detectable |
| INFLATION_HAUTE | 4 | 24 | 36 | 0 | -0.002347 | 0.048418 | -0.050765 | -0.216528 | 0.108579 | 0.261609 | 0.194048 | absence_effet_detectable |
| INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.096758 | 0.024499 | 0.072260 | non estimable | non estimable | 0.588047 | 0.122881 | donnees_insuffisantes |
| RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.107427 | 0.014115 | 0.093312 | -0.138399 | 0.266407 | 0.358925 | 0.259977 | donnees_insuffisantes |
| RESSERREMENT | 4 | 16 | 44 | 0 | 0.019253 | 0.031333 | -0.012080 | -0.190764 | 0.162657 | 0.289817 | 0.041683 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | 0.037655 | 0.027783 | 0.009873 | non estimable | non estimable | 0.713972 | 0.013828 | donnees_insuffisantes |
| COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.028880 | 0.027667 | 0.001213 | -0.168285 | 0.156691 | 0.265954 | 0.004560 | absence_effet_detectable |
| STRESS_CREDIT | 4 | 0 | 60 | 0 | non estimable | 0.028112 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.088059 | 0.014654 | 0.073405 | -0.123621 | 0.377107 | 0.331219 | 0.221622 | donnees_insuffisantes |
| CHOC_ENERGIE | 4 | 18 | 42 | 0 | -0.028759 | 0.052485 | -0.081244 | -0.241551 | 0.082099 | 0.279672 | 0.290496 | donnees_insuffisantes |
| RISQUE_GEO_ELEVE | 4 | 35 | 25 | 0 | 0.054982 | -0.009507 | 0.064489 | -0.094579 | 0.200347 | 0.259960 | 0.248074 | absence_effet_detectable |
| INCERTITUDE_ELEVEE | 4 | 38 | 22 | 0 | 0.048896 | -0.007788 | 0.056684 | -0.077366 | 0.207336 | 0.265954 | 0.213133 | absence_effet_detectable |

### combined — without_news

| Étiquette | Offset | n vrai | n faux | NA | IC vrai | IC faux | Écart | IC bas | IC haut | MDE | Δ absolu / MDE | Conclusion |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INFLATION_HAUTE | 0 | 23 | 38 | 0 | -0.009629 | 0.065150 | -0.074779 | -0.250454 | 0.078392 | 0.317688 | 0.235384 | absence_effet_detectable |
| INFLATION_BASSE | 0 | 4 | 57 | 0 | 0.141109 | 0.029645 | 0.111464 | non estimable | non estimable | 0.621997 | 0.179203 | donnees_insuffisantes |
| RALENTISSEMENT | 0 | 10 | 50 | 1 | 0.088627 | 0.026699 | 0.061928 | -0.240868 | 0.340567 | 0.416564 | 0.148665 | donnees_insuffisantes |
| RESSERREMENT | 0 | 16 | 45 | 0 | 0.013035 | 0.045459 | -0.032424 | -0.195646 | 0.127833 | 0.350017 | 0.092635 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 0 | 2 | 59 | 0 | 0.160908 | 0.032753 | 0.128155 | non estimable | non estimable | 0.864599 | 0.148225 | donnees_insuffisantes |
| COURBE_INVERSEE | 0 | 22 | 39 | 0 | 0.008201 | 0.053174 | -0.044973 | -0.223641 | 0.125700 | 0.320636 | 0.140262 | absence_effet_detectable |
| STRESS_CREDIT | 0 | 0 | 61 | 0 | non estimable | 0.036954 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 0 | 7 | 54 | 0 | 0.129208 | 0.024996 | 0.104212 | -0.209829 | 0.496381 | 0.483070 | 0.215729 | donnees_insuffisantes |
| CHOC_ENERGIE | 0 | 17 | 44 | 0 | -0.032996 | 0.063981 | -0.096977 | -0.252556 | 0.050886 | 0.343404 | 0.282398 | donnees_insuffisantes |
| INFLATION_HAUTE | 1 | 23 | 38 | 0 | -0.019771 | 0.053122 | -0.072894 | -0.260555 | 0.098874 | 0.327821 | 0.222358 | absence_effet_detectable |
| INFLATION_BASSE | 1 | 4 | 57 | 0 | 0.126511 | 0.018559 | 0.107951 | non estimable | non estimable | 0.641837 | 0.168191 | donnees_insuffisantes |
| RALENTISSEMENT | 1 | 9 | 51 | 1 | 0.088236 | 0.016913 | 0.071322 | -0.105756 | 0.305356 | 0.448638 | 0.158975 | donnees_insuffisantes |
| RESSERREMENT | 1 | 17 | 44 | 0 | -0.015304 | 0.041456 | -0.056760 | -0.251401 | 0.131138 | 0.354357 | 0.160177 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 1 | 3 | 58 | 0 | 0.199656 | 0.016637 | 0.183019 | non estimable | non estimable | 0.734712 | 0.249103 | donnees_insuffisantes |
| COURBE_INVERSEE | 1 | 22 | 39 | 0 | 0.006082 | 0.036670 | -0.030588 | -0.206851 | 0.140026 | 0.330863 | 0.092450 | absence_effet_detectable |
| STRESS_CREDIT | 1 | 0 | 61 | 0 | non estimable | 0.025638 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 1 | 11 | 50 | 0 | 0.099472 | 0.009395 | 0.090077 | -0.346460 | 0.512665 | 0.413248 | 0.217973 | donnees_insuffisantes |
| CHOC_ENERGIE | 1 | 16 | 45 | 0 | -0.043829 | 0.050337 | -0.094166 | -0.303457 | 0.065997 | 0.361182 | 0.260716 | donnees_insuffisantes |
| INFLATION_HAUTE | 2 | 24 | 37 | 0 | -0.013189 | 0.056436 | -0.069626 | -0.253598 | 0.101151 | 0.324886 | 0.214308 | absence_effet_detectable |
| INFLATION_BASSE | 2 | 4 | 57 | 0 | 0.128133 | 0.022089 | 0.106044 | non estimable | non estimable | 0.641165 | 0.165392 | donnees_insuffisantes |
| RALENTISSEMENT | 2 | 9 | 51 | 1 | 0.103208 | 0.017899 | 0.085309 | -0.234608 | 0.348780 | 0.448169 | 0.190350 | donnees_insuffisantes |
| RESSERREMENT | 2 | 18 | 43 | 0 | 0.010597 | 0.036764 | -0.026167 | -0.226398 | 0.165283 | 0.347990 | 0.075196 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 2 | 4 | 57 | 0 | 0.012496 | 0.030204 | -0.017708 | non estimable | non estimable | 0.641165 | 0.027619 | donnees_insuffisantes |
| COURBE_INVERSEE | 2 | 23 | 38 | 0 | 0.017645 | 0.035941 | -0.018297 | -0.203151 | 0.155159 | 0.327477 | 0.055871 | absence_effet_detectable |
| STRESS_CREDIT | 2 | 0 | 61 | 0 | non estimable | 0.029043 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 2 | 11 | 50 | 0 | 0.090118 | 0.015606 | 0.074512 | -0.330610 | 0.400983 | 0.412815 | 0.180497 | donnees_insuffisantes |
| CHOC_ENERGIE | 2 | 18 | 43 | 0 | -0.022451 | 0.050598 | -0.073050 | -0.297711 | 0.109043 | 0.347990 | 0.209918 | donnees_insuffisantes |
| INFLATION_HAUTE | 3 | 24 | 37 | 0 | -0.006120 | 0.052218 | -0.058338 | -0.225377 | 0.105368 | 0.285868 | 0.204073 | absence_effet_detectable |
| INFLATION_BASSE | 3 | 3 | 58 | 0 | 0.193079 | 0.020792 | 0.172288 | non estimable | non estimable | 0.645800 | 0.266782 | donnees_insuffisantes |
| RALENTISSEMENT | 3 | 11 | 49 | 1 | 0.100671 | 0.012843 | 0.087828 | -0.187838 | 0.281081 | 0.363906 | 0.241349 | donnees_insuffisantes |
| RESSERREMENT | 3 | 18 | 43 | 0 | 0.017924 | 0.034012 | -0.016088 | -0.199381 | 0.179288 | 0.306198 | 0.052541 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 3 | 3 | 58 | 0 | -0.013237 | 0.031463 | -0.044700 | non estimable | non estimable | 0.645800 | 0.069217 | donnees_insuffisantes |
| COURBE_INVERSEE | 3 | 23 | 38 | 0 | 0.029734 | 0.028981 | 0.000752 | -0.153496 | 0.150320 | 0.288149 | 0.002611 | absence_effet_detectable |
| STRESS_CREDIT | 3 | 0 | 61 | 0 | non estimable | 0.029265 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 3 | 13 | 48 | 0 | 0.046468 | 0.024606 | 0.021862 | -0.183433 | 0.217440 | 0.341020 | 0.064107 | donnees_insuffisantes |
| CHOC_ENERGIE | 3 | 18 | 43 | 0 | -0.028790 | 0.053567 | -0.082357 | -0.263327 | 0.086522 | 0.306198 | 0.268967 | donnees_insuffisantes |
| INFLATION_HAUTE | 4 | 24 | 36 | 0 | -0.002347 | 0.048418 | -0.050765 | -0.216528 | 0.108579 | 0.261609 | 0.194048 | absence_effet_detectable |
| INFLATION_BASSE | 4 | 3 | 57 | 0 | 0.096758 | 0.024499 | 0.072260 | non estimable | non estimable | 0.588047 | 0.122881 | donnees_insuffisantes |
| RALENTISSEMENT | 4 | 9 | 51 | 0 | 0.107427 | 0.014115 | 0.093312 | -0.138399 | 0.266407 | 0.358925 | 0.259977 | donnees_insuffisantes |
| RESSERREMENT | 4 | 16 | 44 | 0 | 0.019253 | 0.031333 | -0.012080 | -0.190764 | 0.162657 | 0.289817 | 0.041683 | donnees_insuffisantes |
| ASSOUPLISSEMENT | 4 | 2 | 58 | 0 | 0.037655 | 0.027783 | 0.009873 | non estimable | non estimable | 0.713972 | 0.013828 | donnees_insuffisantes |
| COURBE_INVERSEE | 4 | 22 | 38 | 0 | 0.028880 | 0.027667 | 0.001213 | -0.168285 | 0.156691 | 0.265954 | 0.004560 | absence_effet_detectable |
| STRESS_CREDIT | 4 | 0 | 60 | 0 | non estimable | 0.028112 | non estimable | non estimable | non estimable | non estimable | non estimable | donnees_insuffisantes |
| STRESS_MARCHE | 4 | 11 | 49 | 0 | 0.088059 | 0.014654 | 0.073405 | -0.123621 | 0.377107 | 0.331219 | 0.221622 | donnees_insuffisantes |
| CHOC_ENERGIE | 4 | 18 | 42 | 0 | -0.028759 | 0.052485 | -0.081244 | -0.241551 | 0.082099 | 0.279672 | 0.290496 | donnees_insuffisantes |

## 5. Portée du test et disponibilité du module

Ce test rétrospectif reste exploratoire : variables macro choisies en connaissant l'histoire, délais approximatifs et archives GPR/EPU sans anciens millésimes certifiés. Le panel et les modèles cinq semaines gardent leurs limites historiques, notamment l'univers conditionné à une cible observée ; ce travail ne corrige ni leur univers, ni leur exécution, ni leur PnL. Aucune preuve de gain de rendement ne peut être déduite d'une association d'IC.

Le moteur macro peut être testé immédiatement sur feature/macro-engine, avec le cache de référence local. Le code de ce test est disponible sur research/macro-conditional-ic ; les données requises restent locales et ne sont pas publiées dans Git. Pour une vraie évaluation future propre, SPEC.md fixe le départ à novembre 2026. Toute future modification de génération d'ordres réels reste soumise au mode fantôme pendant au moins un rééquilibrage et au tableau comparatif production/nouvelle version validé précédemment. Cette livraison ne génère ni ne modifie aucun ordre.

## 6. Reproduction et arrêt

```powershell
.venv/Scripts/python.exe -m research.macro_conditional_ic.prepare
.venv/Scripts/python.exe -m research.macro_conditional_ic.preregister
# Commit, tag et push obligatoires avant l’étape suivante.
.venv/Scripts/python.exe -m research.macro_conditional_ic.infer
```

Les étapes de préparation refusent l'écrasement des données déjà présentes. Pour reproduire l'inférence sur les fichiers déjà archivés, choisir un nouveau répertoire --output-dir ; le garde-fou vérifie les fichiers du tag et les empreintes. Ne pas recréer ni déplacer le tag. Les dépendances existantes macro suffisent ; aucune dépendance du cœur n'est modifiée.

Sources méthodologiques et hypothèses de puissance : voir le protocole préenregistré et ses références NIST/Künsch/SciPy. Aucun paramètre n'a été choisi d'après les IC conditionnels. **Arrêt demandé. Aucune fusion, aucune PR de recherche et aucune règle de portefeuille.**

## 7. Vérifications de livraison

- **177 tests passent** : 52 du cœur, 118 du moteur macro et 7 tests du protocole/recherche ; exécution complète avant le tag et avant les résultats conditionnels (144,23 secondes).
- `ruff check macro_engine research/macro_conditional_ic` et `ruff format --check macro_engine research/macro_conditional_ic` passent (30 fichiers Python).
- Les tests de statistique avant le tag utilisent exclusivement des données synthétiques ; le calcul réel commence après la confirmation du tag distant. Le manifeste d'exécution constate le commit fc3d450 avec un arbre propre.
- Vérifications après calcul : empreintes de toutes les sorties, identité des 200 MDE/effectifs préenregistrés, égalité des contrastes communs aux ablations, jointures strictement antérieures sur les 699 966 lignes, et réconciliation indépendante des moyennes avec les IC par date.
- `SPEC.md`, les fichiers du moteur macro et les fichiers `src/` sont inchangés par cette recherche. Les nouveaux fichiers sont limités à `research/macro_conditional_ic/` et aux documents agrégés dans `docs/macro_engine/`.
- La PR n°9 reste ouverte sur `feature/macro-engine`. Les commits de recherche sont poussés sur `research/macro-conditional-ic`, sans PR ni fusion. Les prédictions, données actions, étiquettes et caches restent ignorés par Git.
