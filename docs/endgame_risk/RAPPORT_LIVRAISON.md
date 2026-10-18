# Livraison — pilotage de fin de challenge

18 octobre 2026. Branche **tools/endgame-risk**, depuis main **1bda389**.

**Outil préparé ; calculs sur le portefeuille réel bloqués**, conformément au choix
validé par l'utilisateur. Les allocations en attente d'exécution restent distinctes
des positions détenues. Le cash déclaré doit être rapproché avec le cash réservé
et les exécutions. Les déclarations privées sont conservées uniquement sous
`outputs/endgame_risk/`, hors Git.

Fonctions disponibles lorsque les entrées seront complètes : poids actifs USD
contre le WLS entier ; TE annualisée via la fonction Ledoit-Wolf inchangée du cœur ;
contributions marginales et totales par ligne, secteur, pays et devise ; classement
des 15 principales contributions ; leviers homogènes ×0,5, ×0,75 et ×1,5 avec
contrôles des règles fournies ; recherche du plus petit nombre de lignes à alléger
pour réduire la TE d'au moins moitié. La recherche distingue un minimum établi à
tolérance numérique, une solution non prouvée minimale et une impossibilité de
l'objectif avec des ventes seules. Aucun ordre ni quantité à exécuter n'est exporté.

Blocages constatés dans les fichiers présents : historiques limités à
**84,170392 % du poids WLS**, une seule date de FX par devise disponible,
métadonnées pays et unités de prix absentes, devises très incomplètes, conventions
et composition datée à vérifier. Le dernier niveau d'indice WLS enregistré date du
**7 octobre 2026**. La TE complète utilisera la composition WLS courante et les
historiques USD de ses composantes ; ce niveau d'indice ancien ne sera pas prolongé
par un proxy. Les **dates de résultats d'ici au 13 novembre sont indisponibles**
dans les exports exploitables ; aucune date n'est inventée.

Validation : **20 tests passent**, exclusivement sur données synthétiques, dont un
parcours complet et un parcours bloqué, ainsi que conversion FX historique,
troncature, contributions signées, raccordement du cash, cardinalité minimale et
échec du solveur. **Ruff et formatage passent**. Aucun nouveau test de
`research/macro-conditional-ic` n'est lancé. Aucun fichier existant du cœur, de la
CI, des dépendances ou de la recherche n'est modifié. La PR n°9 reste ouverte pour
relecture humaine ; aucune PR ou fusion supplémentaire n'est effectuée.

Formats et commandes : [README.md](README.md). Un contrôle des données manquantes
retourne le statut `blocked`, un rapport court et un manifeste avec empreintes ; il
ne produit ni TE, ni poids réels, ni allègement chiffré. **Arrêt à cette livraison.**
