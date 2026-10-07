# Règles du challenge et contradictions à résoudre

État au **7 octobre 2026**. Ce relevé sert à configurer le lab et les tickets
proposés ; il ne remplace pas une confirmation de Bloomberg sur les points
contradictoires. Aucun message à Bloomberg n'a été envoyé dans cette tâche.

## Sources reçues et niveau de certitude

- Le texte des **Trading Challenge Terms & Conditions**, collé par l'utilisateur
  le 7 octobre : paragraphes d'ouverture, Procedures et Winner Selection.
- Le **Trader's Handbook 2026**, PDF de 20 pages fourni par l'utilisateur :
  règles p. 4 et 14, calendrier p. 6, TMSG p. 9 à 13, Relative P&L p. 18.
- Le **mail de bienvenue 2026**, fourni dans la conversation : calendrier,
  starting positions, activation du réseau et droit de saisie du capitaine.
- La [page publique Bloomberg for Education](https://portal.bloombergforeducation.com/trading_challenges/13),
  consultée le 7 octobre.

Les sources originales restent à leur emplacement local ; ne pas copier le
handbook complet ni ses captures dans le dépôt. Les références de pages permettent
à l'équipe de vérifier ce relevé sur son document.

## Règles concordantes ou explicites dans les Terms

| Élément | Lecture opérationnelle |
|---|---|
| Capital initial | 1 000 000 USD notionnels, simulation |
| Univers | Actions membres du WLS Price Return Index ; ETF interdits |
| Positions | Long-only ; aucun levier ; pas de short |
| Concentration | 20 % maximum du notional par position ; 200 000 USD au départ |
| Saisie | Trades via Terminal, par le capitaine uniquement, dans TMSG |
| Classement | Plus haut Relative P&L selon la définition TMSG Help → Calculations |
| Égalité | Départage par Absolute Return selon TMSG |
| Communication officielle | MSG sur le Terminal |
| Début | 12 octobre 2026 à 9 h New York, soit 15 h Paris |

Le plafond interne du dépôt reste 18 %. Il n'est pas une règle Bloomberg.
Relever dans TMSG le traitement des variations de valeur et la consolidation de
plusieurs idées sur la même société. Le libellé du handbook « investissements »
est moins précis que le notional des Terms : ne pas inventer un dénominateur.

## Contradictions qui changent les décisions

| Sujet | Terms / page publique / handbook | Mail de bienvenue | Plan prudent en attendant confirmation |
|---|---|---|---|
| Déploiement initial | Terms : investir tout le million pendant la première semaine | Au moins un trade ; pas nécessaire d'investir tout le capital | Préparer un déploiement complet |
| Deadline initiale | Terms et page : 16 octobre, 23 h 59 New York | 16 octobre, 16 h New York | Terminer avant 16 octobre, 22 h Paris avec marge |
| Fin | Terms et page : 13 novembre, 17 h New York ; handbook : vendredi 13 | 14 novembre, 16 h New York | Planifier jusqu'au vendredi 13, avant 23 h Paris |

Le texte contractuel et le mail ne sont pas cohérents. Le plan choisit la
contrainte la plus exigeante et la première échéance, sans prétendre trancher
définitivement cette divergence. Le capitaine doit demander une confirmation
écrite via MSG. Il peut demander en une fois :

1. Le million doit-il être investi en totalité avant le 16 octobre, ou un trade
   suffit-il ? Quel cash technique résiduel dû aux arrondis est accepté ?
2. L'échéance initiale est-elle 16 h ou 23 h 59 New York ?
3. La fin est-elle le 13 novembre à 17 h ou le 14 à 16 h New York ?

## Exécution réelle à reproduire dans le lab

Le capitaine se connecte avec son UUID, ouvre `TMSG <GO>` et choisit le réseau
régional. Le mail indique l'ajout automatique au début du challenge. Vérifier
le réseau actif, l'identité de l'équipe et le cash initial lorsqu'ils deviennent
disponibles ; les autres étudiants n'ont pas le droit de saisie décrit.

Un BUY contient le titre, le réseau du challenge et un **montant d'investissement
en USD**. TMSG calcule le nombre d'unités achetables ; le débit réel peut différer
légèrement du montant demandé. Le parcours de vente du handbook ferme une idée
existante via `Close Idea`. Aucune possibilité de vente partielle n'est démontrée
par les documents reçus.

Le handbook indique environ **20 minutes** de traitement et une publication
différée des débits/crédits dans Show History. Ce délai est une indication, pas
une garantie de prix ou de remplissage. Réserver le cash des achats soumis,
attendre les crédits des ventes, interdire les doubles saisies et rapprocher les
idées, positions et montants exécutés. Les stop-loss/take-profit optionnels
déclenchent des clôtures automatiques : ils nécessitent une décision et un suivi
explicites, pas une activation par défaut.

## Paramètres encore absents

- Formule du Relative P&L, agrégation des idées, traitement du cash, du FX et des
  dates d'entrée/sortie : les Terms renvoient à TMSG Help → Calculations.
- Commissions, spread, autres coûts éventuels et traitement des dividendes :
  aucun barème n'est donné dans les pièces fournies. Vérifier plutôt que supposer
  un coût nul ou reprendre un tarif de courtier.
- Prix utilisé et traitement exact de la période d'environ vingt minutes,
  marchés fermés, annulations et ventes partielles éventuelles.
- Tolérance de cash résiduel pour l'exigence de déploiement complet, limites
  réévaluées et titres devenant non admissibles.

Pour les relever, utiliser les pages Help et Calculations de TMSG et les paramètres
du réseau du capitaine. Une simulation financière interne de NAV et TE reste
utile, mais ne certifie pas le score officiel tant que son calcul n'est pas
reproduit et rapproché d'un exemple TMSG.
