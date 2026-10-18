# Rapport macro — étapes 03 et 04

Date de requête : **2026-10-16, 23 h 59 UTC**. Calcul local effectué le 18 octobre 2026. Branche : `feature/macro-engine`. Code de calcul : `f2d8329` (les commits suivants peuvent uniquement compléter ce rapport).

Les étapes 03 et 04 sont terminées. Aucun classement de H et R n'est fusionné. R strict n'est pas construit (D003). Les tableaux décrivent des distances ; aucune interprétation économique ou financière n'est ajoutée.

## 1. Cache de référence, périmètre et traçabilité

D006 est appliquée dans `config.py` et `reference.py` : cache unique **20261018T143956.868547Z**. Chargement hors ligne, sans recherche du cache le plus récent, sans collecte automatique et sans réécriture. Le collecteur refuse également toute nouvelle écriture dans ce répertoire.

Chaque chargement vérifie d'abord les ancres du manifeste et du registre, puis les 14 téléchargements bruts, les 10 séries normalisées et les deux tables ALFRED. Les Parquet sont désérialisés depuis les octets déjà vérifiés, pour éviter une modification entre contrôle et lecture. Les autres fichiers auxiliaires du cache ne sont pas utilisés par ces étapes. Les empreintes du code au moment de la collecte restent une provenance ; elles ne sont pas remplacées par celles du nouveau code.

| Élément | SHA256 |
| --- | --- |
| SPEC.md (inchangé) | 6b3e47b7d1119c2edb4e07dd6b79d19e371e889aac8a3781a15e1cb5fb44fce5 |
| Manifeste immuable | 032337011be194aea7231227f61b881d0d57ece9119802820842aad849580c57 |
| Registre immuable | 0f6338dc061df3fd068a181deb539c140e8ded075acf6895e9a936fb9510b39f |

Implémentation ajoutée : `pit.py` (millésimes, disponibilités, propagation), `transform.py` (transformations), `state.py` (espaces quotidiens séparés), `normalize.py` (normalisation à la requête), `analogues.py` (distances et épisodes), `reference.py` (verrou de lecture) et leurs tests. La configuration et le refus d'écriture du collecteur sont les seuls ajustements aux modules macro déjà présents. Aucun fichier du cœur quant-lab, aucune CI, aucun tag de production et aucun paramètre figé de SPEC.md n'ont été modifiés. Aucune nouvelle décision de conception n'a été nécessaire.

## 2. État quotidien et normalisation

**Première distance H strict : 1992-01-27**, soit la 1 260e séance complète depuis le premier état du 1987-02-03. La séance complète précédente ne produit aucune distance. La construction indépendante à une date historique utilise uniquement les informations autorisées pour cette date.

| Combinaison | Variables | Blocs | Premier état complet | Séances complètes au 16/10/2026 | Première séance avec 1 260 états complets | Candidats éligibles |
| --- | --- | --- | --- | --- | --- | --- |
| H strict avec GPR/EPU | 9 | 6 | 1987-02-03 | 9986 | 1992-01-27 | 9751 |
| H strict sans GPR/EPU | 7 | 5 | 1987-02-03 | 9986 | 1992-01-27 | 9751 |
| H descriptif | 9 | 6 | 1987-02-03 | 9986 | 1992-01-27 | 9751 |
| R descriptif | 10 | 7 | 2007-01-04 | 4962 | 2012-01-03 | 4727 |

La normalisation utilise les vecteurs complets du début de chaque espace jusqu'à t inclus. La même moyenne et le même écart-type sont appliqués à t et aux candidats. Convention numérique : écart-type de population pour la standardisation (`ddof=0`), écart-type d'échantillon pour les vingt log-rendements de volatilité (`ddof=1`). Ces diviseurs ne changent pas les paramètres temporels figés. La variante médiane/IQR reste séparée de la méthode principale.

Les niveaux quotidiens manquants sont propagés uniquement depuis le passé pour les lags en séances ; une série terminée ne génère pas de nouvelles transformations. Les transformations mensuelles utilisent des lags calendaires exacts, sans interpolation et sans déplacement vers un autre mois quand une valeur manque. Une fin de mois WTI non positive bloque explicitement le calcul dès sa disponibilité ; un prix négatif intramensuel ne supprime pas une fin de mois valide.

En strict, CPI et chômage sont transformés sur le millésime ALFRED en vigueur à chaque publication, numérateur et dénominateur inclus. En descriptif, les révisions connues à t sont autorisées et l'historique est reconstruit pour chaque nouvelle requête ; on ne découpe jamais un état descriptif construit avec des révisions futures. La date de première publication sert à placer les observations mensuelles révisées dans l'historique descriptif, leur disponibilité révisée reste explicitement t.

Le cache laisse **16 séances incomplètes**, du 2026-02-11 au 2026-03-05, en raison d'un lag de chômage non calculable. Elles sont exclues des normalisations et des distances, sans imputation de la transformation manquante.

| Variable | Statut / traitement |
| --- | --- |
| CPIAUCNS, UNRATE | PIT_VERIFIED en strict ; valeurs révisées signalées RETROSPECTIVE en descriptif |
| DGS2, T10Y2Y, BAA10Y, SP500, DCOILWTICO | PIT_APPROXIMATED — délais de la section 3.3 |
| GPR, EPU | CONTEMPORARY_INPUT_RETRO_METHOD — M+10 conventionnel ; pas de certification des anciens millésimes (D004) |
| SP500 | Yahoo ^GSPC, source MVP validée (D005), closes non ajustés |
| DTWEXBGS | Uniquement R descriptif, RETROSPECTIVE ; variation alignée sur la séance de référence, disponible rétrospectivement à t. Aucun J+1 reconstruit ni raccord avec un autre indice. |

Le cache ne contient pas les intervalles ALFRED du dollar. Les preuves additionnelles de D003 restent hors calcul. La valeur dollar publiée en dernier pour le 09/10/2026 est propagée jusqu'à t ; aucune observation ultérieure n'est inventée. Les indicateurs approximatifs et GPR/EPU conservent leurs limites : « strict » ne les transforme pas en archives de publications certifiées.

### Vecteur standardisé du 16 octobre 2026

Chaque colonne utilise sa propre population de normalisation. Les espaces H et R ne sont pas comparables par leurs distances.

| Variable | H strict avec GPR/EPU | H strict sans GPR/EPU | H descriptif | R descriptif |
| --- | --- | --- | --- | --- |
| CPIAUCNS | 0.574827539 | 0.574827539 | 0.573745391 | 0.615789341 |
| UNRATE | 0.018540462 | 0.018540462 | 0.020468608 | 0.004250757 |
| DGS2 | 1.245900102 | 1.245900102 | 1.245900102 | 1.382512365 |
| T10Y2Y | -0.709881288 | -0.709881288 | -0.709881288 | -0.743066053 |
| BAA10Y | -1.166877601 | -1.166877601 | -1.166877601 | -1.294644192 |
| SP500 | -0.587224677 | -0.587224677 | -0.587224677 | -0.585320884 |
| DCOILWTICO | 1.197782590 | 1.197782590 | 1.197782590 | 1.156143582 |
| GPR | 1.163601809 | absent | 1.163601809 | 1.381087643 |
| EPU | 1.347345253 | absent | 1.347345253 | 0.819976753 |
| DTWEXBGS | absent | absent | absent | -0.055660717 |

### Poids effectivement utilisés

| Variable | H strict avec GPR/EPU | H strict sans GPR/EPU | H descriptif | R descriptif |
| --- | --- | --- | --- | --- |
| CPIAUCNS | 0.166666666667 | 0.200000000000 | 0.166666666667 | 0.142857142857 |
| UNRATE | 0.166666666667 | 0.200000000000 | 0.166666666667 | 0.142857142857 |
| DGS2 | 0.083333333333 | 0.100000000000 | 0.083333333333 | 0.071428571429 |
| T10Y2Y | 0.083333333333 | 0.100000000000 | 0.083333333333 | 0.071428571429 |
| BAA10Y | 0.083333333333 | 0.100000000000 | 0.083333333333 | 0.071428571429 |
| SP500 | 0.083333333333 | 0.100000000000 | 0.083333333333 | 0.071428571429 |
| DCOILWTICO | 0.166666666667 | 0.200000000000 | 0.166666666667 | 0.142857142857 |
| GPR | 0.083333333333 | absent | 0.083333333333 | 0.071428571429 |
| EPU | 0.083333333333 | absent | 0.083333333333 | 0.071428571429 |
| DTWEXBGS | absent | absent | absent | 0.142857142857 |

Somme des poids : 1 à 1e-12 près dans chaque espace. L'ablation stricte supprime le bloc GPR/EPU et répartit le poids entre les cinq blocs restants.

## 3. Analogues principaux

Paramètres : embargo de 365 jours calendaires ; horizon h = quatre semaines et condition s+h<t ; seuil strictement inférieur au quantile 5 % ; épisode si écart entre candidats retenus <20 séances NYSE ; représentants séparés d'au moins douze mois calendaires ; cinq épisodes au maximum. Les ex æquo sont résolus par date croissante. La distance de Mahalanobis Ledoit-Wolf utilise tous les états standardisés complets jusqu'à t inclus, et ne remplace jamais le classement euclidien pondéré.

Les trois variables « rapprochent » sont celles de plus faible contribution à la distance au carré ; « éloignent » celles de plus forte contribution. La stabilité est donnée sans seuil ajouté : occurrences de la date représentative exacte /9, puis occurrences d'un représentant à l'intérieur de l'intervalle de cet épisode /9, sur les neuf combinaisons prévues. Les périodes d'épisodes sont les bornes des candidats retenus, sans supposer que chaque séance intermédiaire a été retenue.

### H strict avec GPR/EPU

Seuil q=5 % : 0.763105698887. 9751 candidats éligibles ; 488 sous le seuil ; 5 épisodes sélectionnés.

| Rang | Début épisode | Fin épisode | Représentant | Distance | Mahalanobis | 3 rapprochent | 3 éloignent | Stabilité exacte ; intervalle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2018-04-10 | 2018-10-09 | 2018-07-06 | 0.424456594 | 1.692203695 | T10Y2Y, SP500, UNRATE | CPIAUCNS, BAA10Y, EPU | 9/9 ; 9/9 ; épisode présent sans GPR/EPU |
| 2 | 2017-01-18 | 2017-05-01 | 2017-03-29 | 0.574249502 | 1.770991032 | SP500, UNRATE, DCOILWTICO | BAA10Y, CPIAUCNS, T10Y2Y | 6/9 ; 6/9 ; FRAGILE sans GPR/EPU |
| 3 | 2024-04-11 | 2024-08-01 | 2024-07-02 | 0.598739336 | 2.186561192 | BAA10Y, UNRATE, GPR | EPU, DCOILWTICO, T10Y2Y | 9/9 ; 9/9 ; FRAGILE sans GPR/EPU |
| 4 | 2005-10-10 | 2005-11-09 | 2005-10-13 | 0.611603586 | 2.266618958 | SP500, CPIAUCNS, T10Y2Y | EPU, GPR, DCOILWTICO | 9/9 ; 9/9 ; épisode présent sans GPR/EPU |
| 5 | 1990-01-10 | 1990-02-09 | 1990-01-31 | 0.646797495 | 2.422426627 | UNRATE, T10Y2Y, DGS2 | EPU, DCOILWTICO, CPIAUCNS | 6/9 ; 6/9 ; FRAGILE sans GPR/EPU |

### H strict sans GPR/EPU

Seuil q=5 % : 0.452311239968. 9751 candidats éligibles ; 488 sous le seuil ; 5 épisodes sélectionnés.

| Rang | Début épisode | Fin épisode | Représentant | Distance | Mahalanobis | 3 rapprochent | 3 éloignent | Stabilité exacte ; intervalle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2006-01-04 | 2006-08-02 | 2006-05-26 | 0.213545349 | 0.731680957 | UNRATE, SP500, CPIAUCNS | DGS2, BAA10Y, T10Y2Y | 9/9 ; 9/9 |
| 2 | 2004-12-30 | 2005-11-01 | 2005-03-08 | 0.271307919 | 0.600932835 | UNRATE, DGS2, SP500 | CPIAUCNS, T10Y2Y, DCOILWTICO | 4/9 ; 4/9 |
| 3 | 2018-05-10 | 2018-10-10 | 2018-07-27 | 0.354262182 | 1.315445437 | T10Y2Y, UNRATE, SP500 | CPIAUCNS, BAA10Y, DGS2 | 9/9 ; 9/9 |
| 4 | 1996-08-13 | 1996-09-05 | 1996-09-05 | 0.382951766 | 0.788222014 | UNRATE, DGS2, BAA10Y | DCOILWTICO, CPIAUCNS, T10Y2Y | 9/9 ; 9/9 |
| 5 | 1995-02-15 | 1995-03-17 | 1995-03-06 | 0.389139407 | 0.760293782 | UNRATE, BAA10Y, T10Y2Y | CPIAUCNS, DCOILWTICO, DGS2 | 4/9 ; 4/9 |

### H descriptif

Seuil q=5 % : 0.764018046066. 9751 candidats éligibles ; 488 sous le seuil ; 5 épisodes sélectionnés.

| Rang | Début épisode | Fin épisode | Représentant | Distance | Mahalanobis | 3 rapprochent | 3 éloignent | Stabilité exacte ; intervalle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2018-04-10 | 2018-10-09 | 2018-07-06 | 0.421836091 | 1.682514181 | UNRATE, T10Y2Y, SP500 | CPIAUCNS, BAA10Y, EPU | 9/9 ; 9/9 |
| 2 | 2017-01-18 | 2017-05-01 | 2017-03-29 | 0.574226160 | 1.779494027 | SP500, UNRATE, DCOILWTICO | BAA10Y, CPIAUCNS, T10Y2Y | 6/9 ; 6/9 |
| 3 | 2024-04-11 | 2024-08-01 | 2024-07-02 | 0.596915142 | 2.197824868 | UNRATE, BAA10Y, GPR | EPU, DCOILWTICO, T10Y2Y | 9/9 ; 9/9 |
| 4 | 2005-10-10 | 2005-11-09 | 2005-10-13 | 0.609827472 | 2.269634113 | UNRATE, SP500, CPIAUCNS | EPU, GPR, DCOILWTICO | 9/9 ; 9/9 |
| 5 | 1990-01-10 | 1990-02-09 | 1990-01-31 | 0.648458672 | 2.420786409 | T10Y2Y, UNRATE, DGS2 | EPU, DCOILWTICO, CPIAUCNS | 6/9 ; 6/9 |

### R descriptif

Seuil q=5 % : 0.684932554044. 4727 candidats éligibles ; 237 sous le seuil ; 3 épisodes sélectionnés.

| Rang | Début épisode | Fin épisode | Représentant | Distance | Mahalanobis | 3 rapprochent | 3 éloignent | Stabilité exacte ; intervalle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2018-04-23 | 2018-10-09 | 2018-06-14 | 0.366393515 | 1.273966002 | DTWEXBGS, SP500, T10Y2Y | CPIAUCNS, EPU, BAA10Y | 9/9 ; 9/9 |
| 2 | 2017-01-18 | 2017-04-07 | 2017-03-16 | 0.530348442 | 1.679720995 | UNRATE, SP500, DCOILWTICO | BAA10Y, T10Y2Y, GPR | 6/9 ; 6/9 |
| 3 | 2024-04-12 | 2024-07-31 | 2024-07-03 | 0.569542470 | 2.131349032 | UNRATE, BAA10Y, SP500 | EPU, DCOILWTICO, DTWEXBGS | 9/9 ; 9/9 |

**Trois épisodes seulement : les rangs 4 et 5 ne sont pas disponibles avec les règles figées. Aucun seuil ni délai n'est relâché.**

Le marquage de fragilité applique une correspondance mécanique par recouvrement des intervalles d'épisodes entre les deux classements stricts. Il n'ajoute aucune fenêtre de tolérance et ne compare pas les valeurs de distance entre leurs espaces différents. Les épisodes stricts représentés par 2017-03-29, 2024-07-02 et 1990-01-31 sont absents du classement de l'ablation selon cette correspondance.

## 4. Contributions complètes

Contributions en pourcentage à la distance euclidienne au carré ; somme non arrondie égale à 100 % à la tolérance 1e-9 sur les fractions. Les écarts de somme affichée viennent de l'arrondi.

### H strict avec GPR/EPU

| Représentant | CPIAUCNS | UNRATE | DGS2 | T10Y2Y | BAA10Y | SP500 | DCOILWTICO | GPR | EPU |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-07-06 | 32.06404 | 1.20384 | 10.05900 | 0.09251 | 24.79274 | 0.83240 | 1.86858 | 8.41504 | 20.67185 |
| 2017-03-29 | 19.95584 | 0.65771 | 7.70687 | 19.71470 | 31.68390 | 0.24785 | 2.33965 | 12.22946 | 5.46402 |
| 2024-07-02 | 4.03405 | 0.60501 | 8.06606 | 11.16979 | 0.57964 | 2.59874 | 32.77930 | 2.37720 | 37.79022 |
| 2005-10-13 | 0.16400 | 0.57982 | 4.11008 | 0.40101 | 6.98296 | 0.00104 | 8.46325 | 20.70779 | 58.59003 |
| 1990-01-31 | 13.02238 | 0.00000 | 0.67499 | 0.35856 | 1.18635 | 5.49333 | 13.32773 | 10.80992 | 55.12673 |

### H strict sans GPR/EPU

| Représentant | CPIAUCNS | UNRATE | DGS2 | T10Y2Y | BAA10Y | SP500 | DCOILWTICO |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2006-05-26 | 6.38389 | 0.00000 | 35.96526 | 15.78922 | 23.90603 | 6.31290 | 11.64270 |
| 2005-03-08 | 63.29941 | 0.00000 | 0.02046 | 23.24861 | 3.38760 | 0.27218 | 9.77174 |
| 2018-07-27 | 47.22952 | 2.07380 | 17.32819 | 0.15936 | 27.60260 | 2.38760 | 3.21892 |
| 1996-09-05 | 33.35818 | 0.00000 | 0.09243 | 4.50906 | 0.50588 | 1.44439 | 60.09007 |
| 1995-03-06 | 45.44947 | 0.00000 | 6.21592 | 1.61795 | 0.05444 | 3.04609 | 43.61615 |

### H descriptif

| Représentant | CPIAUCNS | UNRATE | DGS2 | T10Y2Y | BAA10Y | SP500 | DCOILWTICO | GPR | EPU |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-07-06 | 32.43621 | 0.00000 | 10.18437 | 0.09366 | 25.10173 | 0.84277 | 1.89187 | 8.51991 | 20.92948 |
| 2017-03-29 | 19.94059 | 0.66650 | 7.70750 | 19.71630 | 31.68648 | 0.24787 | 2.33984 | 12.23045 | 5.46447 |
| 2024-07-02 | 4.05531 | 0.00000 | 8.11543 | 11.23817 | 0.58319 | 2.61464 | 32.97995 | 2.39176 | 38.02155 |
| 2005-10-13 | 0.16481 | 0.00000 | 4.13406 | 0.40335 | 7.02370 | 0.00105 | 8.51262 | 20.82859 | 58.93182 |
| 1990-01-31 | 12.94479 | 0.52264 | 0.67154 | 0.35673 | 1.18028 | 5.46523 | 13.25953 | 10.75461 | 54.84466 |

### R descriptif

| Représentant | CPIAUCNS | UNRATE | DGS2 | T10Y2Y | BAA10Y | SP500 | DCOILWTICO | GPR | EPU | DTWEXBGS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-06-14 | 24.98215 | 6.50152 | 4.88400 | 0.21402 | 15.62935 | 0.02195 | 8.51552 | 15.48527 | 23.76530 | 0.00092 |
| 2017-03-16 | 13.58279 | 0.34478 | 10.19105 | 20.50042 | 23.30259 | 1.13835 | 1.83826 | 19.65973 | 5.48762 | 3.95440 |
| 2024-07-03 | 2.58824 | 0.00000 | 9.62180 | 10.07756 | 0.50374 | 1.75260 | 24.27725 | 3.60231 | 35.77631 | 11.80019 |

## 5. Les neuf combinaisons de sensibilité

Dates classées par distance croissante à l'intérieur de chaque ligne ; les classements de différents espaces ne sont pas fusionnés.

### H strict avec GPR/EPU

| Séparation (mois) | q (%) | Nombre | Représentants (ordre du classement) | Dates exactes du classement principal conservées |
| --- | --- | --- | --- | --- |
| 6 | 2.5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 2004-11-29 | 4/5 |
| 6 | 5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 2004-11-29 | 4/5 |
| 6 | 10 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 2004-11-29 | 4/5 |
| 12 | 2.5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 1990-01-31 | 5/5 |
| 12 | 5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 1990-01-31 | 5/5 |
| 12 | 10 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 1990-01-31 | 5/5 |
| 24 | 2.5 | 4 | 2018-07-06, 2024-07-02, 2005-10-13, 1990-01-31 | 4/5 |
| 24 | 5 | 5 | 2018-07-06, 2024-07-02, 2005-10-13, 1990-01-31, 1995-03-06 | 4/5 |
| 24 | 10 | 5 | 2018-07-06, 2024-07-02, 2005-10-13, 1990-01-31, 1995-03-06 | 4/5 |

### H strict sans GPR/EPU

| Séparation (mois) | q (%) | Nombre | Représentants (ordre du classement) | Dates exactes du classement principal conservées |
| --- | --- | --- | --- | --- |
| 6 | 2.5 | 4 | 2006-05-26, 2005-03-08, 2018-07-27, 1996-09-05 | 4/5 |
| 6 | 5 | 5 | 2006-05-26, 2005-03-08, 2018-07-27, 1996-09-05, 1995-03-06 | 5/5 |
| 6 | 10 | 5 | 2006-05-26, 2018-07-27, 1996-09-05, 1995-03-06, 1990-01-31 | 4/5 |
| 12 | 2.5 | 4 | 2006-05-26, 2005-03-08, 2018-07-27, 1996-09-05 | 4/5 |
| 12 | 5 | 5 | 2006-05-26, 2005-03-08, 2018-07-27, 1996-09-05, 1995-03-06 | 5/5 |
| 12 | 10 | 5 | 2006-05-26, 2018-07-27, 1996-09-05, 1995-03-06, 1990-01-31 | 4/5 |
| 24 | 2.5 | 3 | 2006-05-26, 2018-07-27, 1996-09-05 | 3/5 |
| 24 | 5 | 5 | 2006-05-26, 2018-07-27, 1996-09-05, 1990-01-31, 1987-06-29 | 3/5 |
| 24 | 10 | 5 | 2006-05-26, 2018-07-27, 1996-09-05, 1990-01-31, 1987-06-29 | 3/5 |

### H descriptif

| Séparation (mois) | q (%) | Nombre | Représentants (ordre du classement) | Dates exactes du classement principal conservées |
| --- | --- | --- | --- | --- |
| 6 | 2.5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 2004-11-29 | 4/5 |
| 6 | 5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 2004-11-29 | 4/5 |
| 6 | 10 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 2004-11-29 | 4/5 |
| 12 | 2.5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 1990-01-31 | 5/5 |
| 12 | 5 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 1990-01-31 | 5/5 |
| 12 | 10 | 5 | 2018-07-06, 2017-03-29, 2024-07-02, 2005-10-13, 1990-01-31 | 5/5 |
| 24 | 2.5 | 4 | 2018-07-06, 2024-07-02, 2005-10-13, 1990-01-31 | 4/5 |
| 24 | 5 | 5 | 2018-07-06, 2024-07-02, 2005-10-13, 1990-01-31, 1995-03-06 | 4/5 |
| 24 | 10 | 5 | 2018-07-06, 2024-07-02, 2005-10-13, 1990-01-31, 1995-03-06 | 4/5 |

### R descriptif

| Séparation (mois) | q (%) | Nombre | Représentants (ordre du classement) | Dates exactes du classement principal conservées |
| --- | --- | --- | --- | --- |
| 6 | 2.5 | 3 | 2018-06-14, 2017-03-16, 2024-07-03 | 3/3 |
| 6 | 5 | 5 | 2018-06-14, 2017-03-16, 2024-07-03, 2025-02-14, 2023-10-27 | 3/3 |
| 6 | 10 | 5 | 2018-06-14, 2017-03-16, 2024-07-03, 2025-02-14, 2023-10-27 | 3/3 |
| 12 | 2.5 | 3 | 2018-06-14, 2017-03-16, 2024-07-03 | 3/3 |
| 12 | 5 | 3 | 2018-06-14, 2017-03-16, 2024-07-03 | 3/3 |
| 12 | 10 | 5 | 2018-06-14, 2017-03-16, 2024-07-03, 2020-02-18, 2021-09-20 | 3/3 |
| 24 | 2.5 | 2 | 2018-06-14, 2024-07-03 | 2/3 |
| 24 | 5 | 2 | 2018-06-14, 2024-07-03 | 2/3 |
| 24 | 10 | 3 | 2018-06-14, 2024-07-03, 2021-09-20 | 2/3 |

## 6. Variante robuste médiane / IQR

Même embargo, même construction d'épisodes et mêmes paramètres principaux (douze mois, q=5 %). Cette variante n'a pas servi à modifier le classement principal.

### H strict avec GPR/EPU

| Rang | Début épisode | Fin épisode | Représentant | Distance robuste | Mahalanobis robuste |
| --- | --- | --- | --- | --- | --- |
| 1 | 2018-04-10 | 2018-10-09 | 2018-07-06 | 0.385226050 | 1.637179415 |
| 2 | 2004-10-11 | 2005-01-07 | 2004-11-29 | 0.475042969 | 1.990187333 |
| 3 | 2017-02-03 | 2017-04-12 | 2017-03-29 | 0.486473226 | 1.745153727 |
| 4 | 2024-04-09 | 2024-07-17 | 2024-07-03 | 0.492069344 | 2.148571153 |
| 5 | 1990-01-10 | 1990-02-09 | 1990-01-31 | 0.543950095 | 2.382411168 |

### H strict sans GPR/EPU

| Rang | Début épisode | Fin épisode | Représentant | Distance robuste | Mahalanobis robuste |
| --- | --- | --- | --- | --- | --- |
| 1 | 2005-07-08 | 2006-08-31 | 2006-05-26 | 0.176848342 | 0.704058382 |
| 2 | 2005-03-04 | 2005-06-02 | 2005-03-08 | 0.229210125 | 0.589691480 |
| 3 | 1996-08-13 | 1996-09-05 | 1996-09-05 | 0.323711577 | 0.777211095 |
| 4 | 2018-07-06 | 2018-10-04 | 2018-08-08 | 0.325024555 | 1.067391009 |
| 5 | 1995-02-03 | 1995-03-09 | 1995-03-06 | 0.340465293 | 0.754687858 |

### H descriptif

| Rang | Début épisode | Fin épisode | Représentant | Distance robuste | Mahalanobis robuste |
| --- | --- | --- | --- | --- | --- |
| 1 | 2018-04-23 | 2018-10-09 | 2018-07-06 | 0.360389500 | 1.626303416 |
| 2 | 2024-04-09 | 2024-08-01 | 2024-07-03 | 0.472878125 | 2.158316553 |
| 3 | 2004-10-11 | 2005-02-03 | 2004-11-29 | 0.475042969 | 1.989391171 |
| 4 | 2017-02-10 | 2017-04-07 | 2017-03-29 | 0.486473226 | 1.752947153 |
| 5 | 1990-01-10 | 1990-02-09 | 1990-01-31 | 0.560714031 | 2.380125388 |

### R descriptif

| Rang | Début épisode | Fin épisode | Représentant | Distance robuste | Mahalanobis robuste |
| --- | --- | --- | --- | --- | --- |
| 1 | 2018-04-20 | 2018-10-09 | 2018-07-06 | 0.362850401 | 1.618833613 |
| 2 | 2017-02-03 | 2017-04-07 | 2017-03-15 | 0.489677328 | 1.687269749 |
| 3 | 2024-04-12 | 2024-07-23 | 2024-07-03 | 0.500630400 | 2.075704724 |

## 7. Validation et reproduction

Étape 03 : **49 tests réussis** avant de démarrer l'étape 04. Tests propres aux analogues : **34 réussis**. Validation globale : **135 tests réussis en 127,19 secondes**, soit 52 tests du cœur quant-lab et 83 tests macro. `ruff check macro_engine` et `ruff format --check macro_engine` passent sur les 14 fichiers Python du module.

| Contrôle | Résultat / portée |
| --- | --- |
| Troncature | Six dates × trois espaces pour les états ; six dates × quatre variantes pour les analogues. États, dates de disponibilité, statuts, normalisation, distances et épisodes strictement identiques. |
| D007 | Au 1990-08-15 : états identiques, absence identique de distances et d'analogues ; seuil 1 260 inchangé. |
| Disponibilité | Zéro utilisation avant disponibilité sur tout l'historique strict, pour chaque valeur non manquante ; les statuts approximatifs restent explicites. |
| Interpolation | Constantes entre publications pour les variables mensuelles ; aucun backfill ni interpolation. |
| Pétrole | Injection de zéro ou négatif en fin de mois : erreur ; négatif intramensuel et publication future testés séparément. |
| Échantillons et dollar | Classements séparés H/R ; dollar absent de H ; aucun ancien indice raccordé ; R strict refusé. |
| Normalisation / covariance | Injection de valeurs extrêmes après une date historique : distances, covariance et épisodes inchangés ; reconstruction descriptive obligatoire. |
| Poids / contributions | Sommes contrôlées à 1e-12 / 1e-9 ; formules et top 3 revérifiés. |
| Embargo / épisodes | Tous les candidats à >=365 jours ; h=4 semaines ; limite exacte de 20 séances et séparations calendaires testées. |
| Déterminisme | Reconstruction indépendante : égalité exacte des tableaux et de leurs empreintes. |

Les étiquettes de régime et leur volet de troncature sont différés à l'étape 05, conformément à l'interdiction explicite d'en produire à ce stade. Aucun module de régimes, export final ou rapport HTML n'a été ajouté. Aucun résultat financier, IC ou rendement futur n'est calculé.

Commandes exécutées depuis la racine de la branche :

```powershell
.venv/Scripts/python.exe -m pytest tests macro_engine/tests -o addopts="" -q --basetemp=../pytest_macro_0304_final
.venv/Scripts/python.exe -m ruff check macro_engine
.venv/Scripts/python.exe -m ruff format --check macro_engine
```

Pour reproduire un classement en mémoire, sans collecte ni export :

```python
from macro_engine.reference import load_reference
from macro_engine.state import build_state
from macro_engine.normalize import normalize
from macro_engine.analogues import find_analogues, sensitivity

r = load_reference()
s = build_state(r, "2026-10-16", "H", "strict", include_news=True)
n = normalize(s)
a = find_analogues(n)
print(a.episodes.to_string(index=False))
print(a.fingerprint())
variants = sensitivity(n)
```

| Combinaison | Empreinte du classement + distances éligibles + paramètres |
| --- | --- |
| H strict avec GPR/EPU | 1e9bc199c303bc9e48ef6f02f6a93f709989fc458759a5078013a056b21f9b1e |
| H strict sans GPR/EPU | 0ef9184cadeded5b313ce7bdb6b72f192139c862e7f9a9de7e4537e3c47e2708 |
| H descriptif | d504ca4daac4b69540caa2f33d3909eb2e944d14e7f1d8d2f1662a0c5c3e6895 |
| R descriptif | be313dc5d92a26b2077528fae838e39181e696cc3d2e17252dbb4d970a59c1ce |

| Bibliothèque | Version exécutée |
| --- | --- |
| numpy | 2.5.3 |
| pandas | 3.0.6 |
| scikit-learn | 1.9.1 |
| pandas-market-calendars | 5.5.0 |
| pyarrow | 25.0.1 |
| pytest | 9.1.1 |
| ruff | 0.16.10 |

## 8. Arrêt à la fin de l'étape 04

Le rapport constitue le livrable de revue. Seuls le code macro, les tests et ce rapport sont committés sur feature/macro-engine ; les données restent dans le cache ignoré. Aucune PR nouvelle, fusion ou étape 05 n'est engagée par cette livraison. SPEC.md reste identique au préenregistrement spec-v1.0.
