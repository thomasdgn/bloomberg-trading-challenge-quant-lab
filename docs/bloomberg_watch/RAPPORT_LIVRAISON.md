# Livraison — veille macro Bloomberg prospective

19 octobre 2026. Branche **tools/bloomberg-watch**, créée depuis main **1bda389**
dans un checkout isolé pour préserver les travaux de recherche existants.

**La veille est en place.** Interface locale sur `http://127.0.0.1:8767/`, journal
horodaté, calendrier et rapport quotidien. L'utilisateur a connecté sa session
Bloomberg dans le navigateur ; une lecture intégrale d'un article a été vérifiée.
Le premier point contient **9 observations : 1 relevé Bloomberg et 8 événements
officiels** jusqu'au 13 novembre, avec heures non confirmées laissées inconnues.
Les sources officielles complètent le calendrier sans être présentées comme Bloomberg.

Le suivi quotidien est configuré dans cette discussion à **08 h 30, heure de Paris,
jusqu'au 13 novembre 2026 inclus**. L'ordinateur et l'application doivent rester
ouverts pour les fichiers locaux. Une reconnexion peut être nécessaire si la session
expire. Les états inchangés et blocages déjà signalés ne sont pas répétés.

Chaque ajout conserve son heure de première collecte. Les corrections créent une
version sans réécrire l'ancienne. Faits, avis et interprétation sont distingués.
Une surprise exige un consensus archivé avant publication, de même événement,
date et unité. Les liens aux titres restent thématiques : pas de poids, d'exécution
ou de risque présumés à partir de budgets déclarés.

**17 tests synthétiques passent**, ainsi que Ruff et le formatage. Vérifications :
troncature, intégrité du journal, absence de consensus ex post, fuseaux, import
idempotent, contenus HTML échappés, formulaire local et refus des origines externes.
L'interface réelle et le premier relevé ont été vérifiés dans le navigateur.

Seuls le code, les tests synthétiques et la documentation sont publiés. Les résumés,
sources collectées, liste de suivi et rapports privés restent dans `outputs/`, hors
Git. Aucune dépendance supplémentaire, modification du moteur macro, de son cache,
des recherches ou de la CI. Aucun ordre, nouveau test de recherche, PR ou fusion.

Utilisation : [README.md](README.md). Suivi : [ROUTINE_QUOTIDIENNE.md](ROUTINE_QUOTIDIENNE.md).
