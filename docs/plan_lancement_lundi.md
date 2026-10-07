# Quant lab avant les premiers trades : plan du 7 au 12 octobre 2026

## Cible et limite du périmètre

Livrer une chaîne **données → signaux → risque → poids → tickets USD → contrôles →
rapport**, reproductible et testée, puis une répétition du parcours `TMSG` avec
le capitaine. Les ordres restent soumis à la revue de l'équipe.

Lundi 12 octobre à **15 h Paris** correspond au début officiel à 9 h New York.
Les Terms donnent une échéance initiale au vendredi 16 octobre à 23 h 59 New York,
mais le mail reçu donne 16 h le même jour. **Objectif prudent : portefeuille
entièrement déployé avant le vendredi 16 octobre à 22 h Paris**, avec marge pour
le traitement TMSG. Les Terms exigent tout le million investi ; le mail dit un
seul trade et un déploiement partiel. Ce conflit doit être confirmé par le
capitaine auprès de Bloomberg via MSG ; d'ici là, retenir l'exigence complète.

Les Terms et le handbook donnent une fin le vendredi 13 novembre ; les Terms
précisent 17 h New York, soit 23 h Paris. Le mail indique le samedi 14 à 16 h.
Planifier les décisions avant le vendredi et ne pas compter sur la journée du
samedi. Les écarts sont consignés dans `regles_challenge_2026.md`.
[Calendrier officiel](https://portal.bloombergforeducation.com/trading_challenges/13).

Ce plan est une estimation de travail et une répartition par rôle proposée.
Il ne suppose pas que ces personnes sont déjà assignées ni disponibles.

## Inventaire concret du dépôt

**Mise à jour de cette branche :** l'adaptateur, le risque relatif et l'optimiseur
de référence sont maintenant implémentés ; leur utilisation et leurs limites
figurent dans [reference_v1.md](reference_v1.md). Le tableau ci-dessous décrit
l'état initial du diagnostic du 7 octobre. L'alpha robuste, les ordres et le
backtest restent à réaliser.

| Brique | État constaté | Ce qui manque |
|---|---|---|
| Environnement + CI | Python 3.14, dépendances figées, tests Windows/Linux | CVXPY/solveur non déclarés ni vérifiés sous les deux OS |
| Import ancien WLS | Fonctionnel, provenance, erreurs conservées | Pas le pipeline des historiques/facteurs du 7 octobre |
| Données Bloomberg | CSV audités, sources et conflits documentés | Devises, ajustements, pays/places, métadonnées d'exécution |
| Covariance | Ledoit-Wolf et fonctions PSD, un test | Rendements USD validés et risque relatif contre le WLS |
| Signaux / Elastic Net | Description dans le README | Aucun module implémenté, aucun IC hors échantillon validé |
| Optimisation | Étude dans cette branche | Solveur, contraintes, faisabilité, stabilité, tests |
| Backtest | Mention dans le README | Moteur, coûts, délais, FX, benchmark et placebo |
| Exécution | Aucun module présent ; parcours TMSG décrit dans le handbook | Tickets USD, idées BUY/CLOSE, ordres en attente, cash et réconciliation |
| Rapport quotidien | Aucun orchestrateur présent | Commande unique, journal d'exécution, alertes et suivi relatif |

Les fichiers `src/elastic_net_transversal.py` et `src/backtest.py` annoncés dans
le README restent absents. `src/optimisation.py` fournit désormais la référence
sans alpha. Le quant lab de bout en bout reste à terminer.

## Diagnostic des données

Le diagnostic détaillé est dans `robust_readiness_metrics.json` et peut être
recalculé avec `scripts/audit_robust_readiness.py`.

Depuis la racine du dépôt, pour produire un nouveau rapport local :

```powershell
.\.venv\Scripts\python.exe scripts/audit_robust_readiness.py --output outputs/readiness_2026-10-07.json
```

Le script refuse d'écraser un rapport existant. Ses dates par défaut correspondent
à cette étude ; utiliser `--as-of` et `--cutoff` pour une autre extraction et une
dernière semaine complète différente.

- Univers actuel : **10 420** titres. Historiques : **1 262**, représentant
  **84,1704 %** des poids actuels de l'indice. Cette couverture n'est pas une
  garantie de réplication historique.
- Fenêtre exploratoire : **52 rendements hebdomadaires**, terminant au 2 octobre.
  La semaine du 7 octobre est exclue car incomplète au moment du snapshot.
- **1 255** titres ont au moins 40 observations sur 52 ; il ne reste que
  **37 semaines communes complètes** lorsqu'on les prend tous.
- **1 170** ont 52 observations sur 52. Aucun calendrier n'est complet pour
  tous les 1 262 titres simultanément.
- Ces comptes utilisent la dernière valeur disponible dans chaque semaine.
  Ils ne certifient ni fraîcheur par place, ni prix USD, ni ajustements. Ils
  servent à diagnostiquer la couverture et ne constituent pas des rendements
  validés pour trading.

Il faut sélectionner l'univers selon des règles de données et de liquidité,
puis mesurer le calendrier réellement partagé. Ne pas remplir les trous par zéro
ou appliquer globalement `dropna` sans publier les exclusions. Le module de risque
existant peut sinon perdre beaucoup de dates ou sélectionner un univers inattendu.

Les facteurs sont un snapshot avec quelques captures à -1 mois/-3 mois. Cela ne
permet pas de reconstruire un panel historique d'EPS, qualité et révisions.
Des prix sur dix ans ne suffisent pas à entraîner un Elastic Net transversal
sur ces variables sans fuite d'information. L'univers courant ajoute un biais de
survivance à toute étude rétrospective non corrigée.

## Les prérequis bloquants

### A. Règlement et accès

Le Terminal est accessible et le mail confirme l'inscription. Les Terms et le
handbook fournis fixent le budget, les instruments et les principaux caps.
Restent à relever : définition `Relative P&L` dans l'aide TMSG, frais éventuels,
dividendes/opérations sur titres, change, traitement exact des limites et du cash
résiduel. Résoudre aussi les contradictions du mail avec les Terms.

Le capitaine doit vérifier son UUID, le réseau régional dans `TMSG` et son cash
initial. Le mail prévoit l'ajout automatique du capitaine au réseau au début du
challenge : une absence avant lundi n'est donc pas une preuve d'échec. Le
portefeuille/réseau n'est pas encore confirmé par l'utilisateur. La saisie est
réservée au capitaine ; **ne pas prévoir un autre étudiant comme trader remplaçant
sans changement de droits confirmé par Bloomberg**. Préparer ensemble le parcours
BUY en dollars, CLOSE d'idée et Show History avant les premiers tickets.

### B. Données comparables et disponibles au bon moment

Data doit livrer les devises et sous-unités de prix, la convention d'ajustement
des historiques et celle du benchmark, les FX datés et leur sens, les places/pays,
les règles d'arrondi TMSG et un export de prix/liquidité récent. Le benchmark officiel est **Price
Return** ; traiter séparément ce choix et le crédit éventuel de dividendes dans
la valorisation des positions. Les deux ne sont pas à supposer identiques.

Le prix de clôture du vendredi 9 sera la dernière clôture disponible le lundi
avant ouverture pour certains marchés. Un export lundi matin devra indiquer
quelles places ont déjà coté. Ne pas antidater une décision grâce à un snapshot
plus récent. Bloquer les valeurs dont la convention ou la fraîcheur est inconnue.

### C. Allocation faisable et exécutable

Le risque doit porter sur tous les titres sélectionnés et, au rééquilibrage, tous
les titres encore détenus. Il faut un signal défini, un risque relatif, des caps,
des budgets d'exposition et un minimum réalisable de TE. Le passage en tickets
USD doit réserver le cash engagé, gérer les arrondis TMSG et les frais éventuels,
puis revérifier les positions effectivement obtenues. Une vente en attente ne
finance pas un nouvel achat. Aucun succès du solveur ne suffit seul.

## Deux chemins de livraison

**Chemin idéal** : Data fournit rapidement un panel point-in-time suffisamment
long, les univers historiques et un benchmark cohérent. Construire les labels
futurs à cinq semaines et la validation purgée. Si l'IC est stable, estimer
l'incertitude des alphas et utiliser l'optimiseur robuste complet.

**Chemin réaliste pour lundi** : construire la mécanique complète sur un univers
plus réduit, employer une référence à tracking error minimale et un signal
transparent issu de prix correctement préparés. Momentum 12-1 peut être étudié
avec les historiques existants une fois leurs conventions validées. Les autres
facteurs du snapshot peuvent compléter un classement exploratoire, sans prétendre
avoir démontré un IC historique. La robustesse et les limites d'exposition doivent
réduire l'importance de ces alphas non calibrés.

Sans données de risque valides, le chemin de repli n'est pas exécutable non plus.
Si seules les prévisions sont absentes, un portefeuille de référence sans alpha
peut être envisagé avec l'équipe. Si règles, prix, FX, cash ou droits de saisie ne
sont pas confirmés, on conserve un rapport bloqué et on utilise le délai officiel
pour résoudre les problèmes, sans produire d'ordres trompeusement « prêts ».

## Organisation proposée pour cinq personnes

| Rôle | Livraison prioritaire | Dépendance |
|---|---|---|
| Data / Terminal | Règlement, métadonnées, prix/FX et univers récent | Accès au Terminal |
| Signal | Baseline simple et contrat d'alpha/incertitude | Données prix/variables validées |
| Risque | Calendrier, univers, covariance jointe et TE | Historiques comparables + WLS |
| Optimisation / intégration | Solveur, contraintes, rapport reproductible | Interfaces alpha et risque |
| Backtest / exécution | Simulation, tickets USD, ordres en attente et rapprochement | Règles, frais, données + poids |

La validation doit avoir un responsable et un remplaçant ; la saisie TMSG est
réservée au capitaine, dont la disponibilité doit être assurée.
Les rôles peuvent travailler en parallèle avec des fixtures communes et des
branches dédiées ; aucun nom de contributeur n'est assigné automatiquement.

## Calendrier et critères de sortie

| Date, heure Paris proposée | Livraison | Critère mesurable |
|---|---|---|
| Mercredi 7, fin de journée | Interfaces, méthode V1, tâches et accès | Champs obligatoires et propriétaires de tâches identifiés |
| Jeudi 8, midi | Résoudre les contradictions des règles et préciser prix/FX | Échéances, déploiement, scoring TMSG, frais et conventions confirmés |
| Jeudi 8, soir | Adaptateur de données et baseline | Séries alignées, exclusions motivées, aucune donnée future |
| Vendredi 9, soir | Risque + optimiseur sur fixtures puis données vérifiées | Faisabilité, TE minimale, caps, stabilité et tests verts |
| Samedi 10, soir | Backtest mécanique + stress + tickets USD | Résultats connus sur fixtures, ordres en attente et cash cohérents |
| Dimanche 11, après-midi | Répétition complète et revue Faculty Advisor | Run reproductible, tickets lisibles, aucune anomalie bloquante |
| Dimanche 11, soir | Figer méthode et paramètres | Version Git/config sauvegardées, procédures de repli définies |
| Lundi 12, avant 15 h | Rafraîchir données admissibles et contrôler les ordres | Réconciliation portefeuille, frais/FX/prix et contraintes revérifiés |
| Lundi 12, à partir du début autorisé | Premiers trades puis réconciliation | Ordres validés par équipe, positions/frais identiques au journal |

Ces échéances supposent une disponibilité réelle de l'équipe. Si Data ne livre
pas les conventions jeudi, les autres rôles continuent sur données synthétiques
mais le passage aux ordres est bloqué. Ne pas attendre un backtest à dix ans pour
tester les erreurs élémentaires de cash et d'exécution.

## Définition de « lab fonctionnel et efficace »

Une commande documentée reproduit un run depuis une configuration et des données
datées. Elle produit : univers accepté/exclu, scores et alpha avec statut de
validation, risque et couverture, poids, TE et expositions, coûts, tickets USD,
quantités estimées/réalisées et cash, rapport de stress et journal des fichiers.

La cible de temps d'exécution proposée est de quelques minutes sur le poste de
l'équipe, à mesurer sur l'univers retenu ; aucun benchmark de performance n'a
encore été réalisé. Limiter l'univers, mettre en cache les données préparées avec
leurs empreintes, calculer la factorisation une fois, réutiliser les paramètres du
problème et ajouter un modèle factoriel seulement si un profilage le justifie.

Il doit être impossible d'exporter des ordres si l'un des contrôles essentiels
échoue. Le rapport reste consultable pour expliquer l'échec. Aucun fallback
silencieux ne relâche une règle du challenge ou une limite de concentration.

Un suivi après trade calcule NAV et cash, rapproche les positions au Terminal,
mesure performance relative au benchmark officiel, TE réalisée et expositions,
et enregistre les décisions de rééquilibrage. Une interface graphique est
facultative pour la V1 : rapport HTML/CSV et CLI suffisent si l'équipe sait les lire.

## À différer pour préserver le lancement

- DRO Wasserstein, optimisation dynamique multi-période et CPPI relatif.
- Cardinalité exacte avec solveur mixte entier sur tout le WLS.
- Réseau complexe de modèles et recherche de paramètres sur une très grande grille.
- Interface élaborée et exécution automatisée des trades.
- Claims de top 5 % ou de probabilité de gain sans signal et validation fiables.

La première livraison doit prouver sa reproductibilité et sa conformité mécanique.
La validation statistique du signal reste un chantier distinct, qui peut empêcher
de donner une forte conviction aux trades même avec un logiciel fonctionnel.
