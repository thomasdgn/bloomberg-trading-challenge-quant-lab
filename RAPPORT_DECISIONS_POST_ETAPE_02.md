# Complément documentaire après l'étape 02

**18 octobre 2026 — feature/macro-engine uniquement.**

Aucune implémentation de l'étape 03. Ce document consigne les décisions D003 à D007, les requêtes de preuve du dollar et une borne de faisabilité. SPEC.md et le cache de référence restent inchangés.

## 1. Millésimes réels du dollar

Requête exécutée sur l'API officielle FRED/ALFRED :

    series/vintagedates
    series_id=DTWEXBGS
    realtime_end=2026-10-18
    sort_order=asc
    limit=10000

| Résultat | Valeur |
|---|---|
| Nombre de millésimes | **402** |
| Plus ancien | **2019-02-04** |
| Plus récent | **2026-10-13** |
| Pagination | Tous les 402 éléments reçus, égaux au count déclaré |

Pour calculer la borne demandée sans inventer un délai de publication, une requête de diagnostic complémentaire a récupéré les intervalles de validité par series/observations, output_type=1, sur la période disponible jusqu'au 18/10/2026 : **22 097 lignes**.

Ces réponses sont conservées **hors du module et hors du cache de référence**, comme preuves documentaires locales, sans commit des données ni utilisation comme nouvelle entrée de référence. La clé vient de FRED_API_KEY ; elle n'est ni affichée ni enregistrée.

Documentation primaire : [vintage_dates](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html), [observations et intervalles de validité](https://fred.stlouisfed.org/docs/api/fred/series_observations.html).

## 2. D003 : conséquence pour le MVP

Les règles validées sont inscrites dans DECISIONS.md :

- La disponibilité est le realtime_start du premier millésime contenant l'observation ; statut PIT_VERIFIED.
- Les observations dont la date de référence précède le premier millésime sont RETROSPECTIVE, en mode descriptif uniquement.
- **Le premier millésime date de 2019, donc R est descriptif uniquement dans le MVP**, selon le seuil 2010 fixé par l'utilisateur.
- H ne reçoit pas la variable dollar. Aucun raccord ou changement de série.

Le fait qu'un millésime de 2019 contienne des niveaux depuis 2006 n'autorise pas à reconstruire un R strict depuis 2006, ni à réutiliser ces observations rétrospectives dans une transformation stricte.

## 3. Première borne à laquelle R strict pourrait produire une distance

Le calcul ci-dessous est une analyse documentaire extérieure au module. Il n'implémente ni transformation, ni état, ni normalisation, ni distance de l'étape 03.

| Étape du raisonnement | Date / valeur |
|---|---|
| Première observation de dollar non rétrospective selon D003 | 2019-02-04 |
| Premier millésime contenant cette observation | 2019-02-11 |
| Point initial de la première variation admissible sur 252 séances NYSE | 2019-02-04 |
| Point final, 252 séances NYSE plus tard | 2020-02-04 |
| Première date de disponibilité des deux extrémités | 2020-02-10 |
| Premier état R strict théoriquement possible | 2020-02-10 |
| Historique de normalisation requis | 1 260 états complets, séance de départ incluse |
| **1 260e séance : première borne possible pour une distance** | **2025-02-12** |

Le calendrier est NYSE, calculé avec pandas-market-calendars **5.5.0**, et non par ajout de cinq années calendaires ou de 252 jours ouvrés génériques. Le calcul prend la plus tardive des premières disponibilités des deux observations de dollar ; il ne suppose pas que les cours étaient connus le jour de leur observation.

**Le 12/02/2025 est une borne inférieure conditionnelle, pas une date de livraison certifiée.** Elle suppose un état complet à chaque séance à partir du 10/02/2020 et la disponibilité des neuf autres variables. Leur construction n'est pas exécutée ici. Des trous ou d'autres limites PIT pourraient repousser cette date.

L'embargo de 365 jours ne demande pas un an supplémentaire après les 1 260 états : au terme de cette fenêtre, des candidats suffisamment anciens pourraient déjà exister. L'existence d'épisodes complets et stables reste à vérifier lors des étapes autorisées.

Cette borne ne lève **pas** la décision d'exclure R strict du MVP. Le cache approuvé ne contient pas les intervalles ALFRED du dollar, et les preuves diagnostiques de ce complément ne sont pas ajoutées à ce cache.

## 4. Autres décisions validées

### D004 — GPR et EPU

Acceptés tels que documentés : CONTEMPORARY_INPUT_RETRO_METHOD, règle de disponibilité décrite dans la spec, limitation des millésimes et révisions, ablation avec/sans GPR et EPU en mode strict. Pas de requalification en PIT_VERIFIED.

### D005 — Source S&P 500 du MVP

Yahoo **^GSPC** est désormais la source retenue pour les clôtures d'indice utilisées dans la volatilité réalisée. Le choix n'est plus provisoire.

Le fichier déjà téléchargé dans le cache approuvé est celui-ci ; aucune recollecte n'est nécessaire pour changer la politique de source. Les mentions historiques « fallback » du registre et du manifeste ne sont pas réécrites : elles décrivent la décision en vigueur lors de la collecte. Le changement de libellé opérationnel est différé avec l'implémentation.

### D006 — Cache de référence

Référence unique validée :

    macro_engine/cache/20261018T143956.868547Z/

Contrat à appliquer aux étapes suivantes :

1. Lire uniquement ce cache ; ne pas sélectionner automatiquement un autre répertoire.
2. Vérifier le manifeste et les empreintes.
3. Ne jamais muter ce cache ou ses métadonnées.
4. Exiger une décision explicite avant toute nouvelle collecte de référence.

Une clarification a été demandée entre « épingler dans config.py » et « commit documentaire uniquement ». **Sans levée de cette restriction, aucun fichier Python n'est modifié.** Le pin est consigné ici et dans DECISIONS.md ; la constante et le verrou de lecture doivent être ajoutés avant tout traitement de l'étape 03, une fois la portée confirmée.

### D007 — Troncature quand l'historique est trop court

Pour les dates sans historique suffisant, notamment le cas 1990-08-15 lorsqu'il n'atteint pas le minimum, le test devra vérifier :

- État identique avec les données complètes et les données coupées à t.
- Étiquettes identiques.
- Même absence d'analogues dans les deux exécutions.

Cette absence attendue ne justifie pas de diminuer le minimum de 1 260 séances. Aucun test d'état ou d'analogues n'est ajouté avant la construction autorisée des composants concernés.

## 5. Preuves, contrôle et limites

Preuves locales hors cache de référence :

    ../dollar_vintages_20261018.json
    ../dollar_alfred_documentary_20261018.json
    ../dollar_strict_start_documentary_20261018.json
    ../check_dollar_strict_start.py

L'empreinte SHA-256 de la réponse des intervalles dollar est :

    addb4e20b1d92d570ec99f4678aecbfc8ec6f3cca8c2485d49d43a362f2431b9

Ces fichiers ne sont pas committés. Le script ponctuel sert uniquement à rendre le calcul documentaire reproductible ; ce n'est pas une fonction du module ou une entrée autorisée pour les futures étapes.

Le cache de référence conserve le manifeste du commit de collecte de94172 et le registre dont le SHA-256 est enregistré dans ce manifeste. Les empreintes de tous les fichiers bruts, des observations et des archives CPI/UNRATE sont revérifiées après les requêtes de ce complément.

Les tests de code ne sont pas relancés pour un changement exclusivement documentaire. La dernière validation logicielle reste 64 tests passants, Ruff conforme, telle que rapportée à l'étape 02 ; cela ne constitue pas une validation de nouvelles règles PIT.

## 6. Arrêt

**STOP : l'étape 03 attend exactement le message GO ÉTAPE 03.** Aucun pit.py, transform.py, state.py, calcul d'état, étiquette ou analogue n'est ajouté. Aucun ordre ni changement de portefeuille. Aucun changement de main, de la branche 80/20 ou des tags.
