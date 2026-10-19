# Veille Bloomberg prospective

Branche `tools/bloomberg-watch`, depuis main `1bda389`. Cette veille est indépendante
du moteur macro figé, de ses caches, des recherches terminées et du portefeuille.
Elle n'évalue aucune performance, ne crée aucun signal et ne transmet aucun ordre.

## Utilisation courante

Interface locale : **http://127.0.0.1:8767/**, quand le serveur est lancé.

1. Consulter une source Bloomberg dans le navigateur connecté, ou une source
   officielle. Ne pas interpréter un titre seul comme une lecture de l'article.
2. Ajouter un résumé court avec ses propres mots et le lien. Laisser l'heure source
   inconnue si elle n'est pas vérifiable. Pour un article mis à jour, relever l'heure
   de la version effectivement lue, pas seulement celle de sa publication initiale.
3. Distinguer faits, avis d'analystes et interprétation de l'équipe. Un rapprochement
   avec une ligne du portefeuille indique une pertinence thématique, pas un poids,
   un risque calculé ou une recommandation.
4. Les prochains événements apparaissent dans le calendrier ; les dates sans heure
   confirmée restent sans heure. Les changements de fuseau sont convertis vers Paris.
5. Le rapport quotidien est consultable dans l'interface et archivable en Markdown.

Les articles sont lus dans une session normale du navigateur. Ce module ne contient
ni client HTTP Bloomberg, ni scraper, ni cookies, ni identifiants, ni copie d'article
intégral. L'accès au site ne suppose pas l'accès aux fonctions Terminal ou BQL.
Les calendriers officiels complémentaires sont identifiés comme tels, sans les
présenter comme des données Bloomberg.

## Chronologie et limites

- La collecte reçoit l'heure UTC réelle du programme ; les entrées ne peuvent pas
  imposer leur propre date de collecte. Une information ancienne collectée aujourd'hui
  n'est jamais utilisée dans un rapport arrêté hier.
- Une correction ajoute une version. Les versions antérieures restent dans le journal
  avec une chaîne d'empreintes SHA256 ; les réimportations identiques ne créent pas
  de nouvelle heure de première observation. Le journal est vérifié avant lecture.
- Les empreintes détectent des incohérences et permettent le rapprochement des
  rapports archivés ; elles ne constituent pas une certification indépendante de
  l'heure de publication ni une protection contre une personne réécrivant tous les
  fichiers et toutes les empreintes.
- Une surprise `réalisé − consensus` n'est affichée que si le consensus était déjà
  archivé avant l'heure de publication du réalisé, pour le même événement, la même
  date et la même unité, avec une source consultée intégralement. Un consensus découvert
  après la publication ne permet pas de reconstituer une surprise prospective.
- La surprise brute n'a pas de signe favorable/défavorable automatique. Les révisions
  du précédent sont déclarées séparément, avec leur unité et leur source.
- Les pays, devises ou thèmes non renseignés ne sont pas déduits des codes boursiers.
  Les statuts d'ordres en attente ne deviennent pas des exécutions supposées.
- La couverture est partielle. « Aucun élément enregistré » ne signifie jamais
  « aucun événement ». Une date de résultat d'entreprise n'est ajoutée qu'après
  vérification d'une source ; aucun calendrier d'entreprise n'est inventé.
- Aucun recalcul d'IC historique, réglage de régime ou modification de `SPEC.md`,
  `DECISIONS.md`, `macro_engine/`, `src/` ou du cache de référence.

## Fichiers privés

Tout reste sous `outputs/bloomberg_watch/`, ignoré par Git :

- `observations.jsonl` : journal append-only des résumés et événements ;
- `watchlist.json` : liste déclarative, horodatée, sans montants ni quantités ;
- `reports/<identifiant>/` : rapport, état JSON, copie de la liste et manifeste ;
- `server.json` et journaux techniques : coordonnées du serveur local uniquement.

Ne jamais committer les données de positions, exports Bloomberg ou relevés sources.
Le manifeste archive les empreintes des sorties, du code et de la liste utilisée.
Conserver les versions précédentes de la liste si elle évolue : chaque rapport en
contient une copie. Le serveur écoute exclusivement sur `127.0.0.1`, refuse les
origines externes et protège les ajouts par un jeton de formulaire. Il n'existe pas
de route pour modifier ou supprimer une observation.

## Commandes de reproduction

Python 3.14 et bibliothèque standard ; aucune dépendance de production supplémentaire,
aucune modification de CI. Les tests utilisent les dépendances de développement
existantes (`pytest`, `ruff`). Depuis le checkout de cette branche :

```powershell
python -m tools.bloomberg_watch init
python -m tools.bloomberg_watch serve --port 8767
python -m tools.bloomberg_watch report
python -m pytest tools/bloomberg_watch/tests -q
python -m ruff check tools/bloomberg_watch
python -m ruff format --check tools/bloomberg_watch
```

Les commandes `report` et `serve` partagent le même journal. Les rapports portent
des noms uniques, sans écrasement. Pour une autre liste : initialiser un nouveau
workspace sous `outputs/`, avec `--workspace <chemin> init --watchlist <json>`.

Une observation peut aussi être ajoutée depuis un petit JSON local :

```json
{
  "entity_id": "US-EXEMPLE-2026-10",
  "kind": "calendar",
  "title": "Événement fictif de démonstration",
  "source_url": "https://www.example.org/calendar",
  "source_access": "read_full",
  "source_version": "unknown",
  "event_date": "2026-11-06",
  "fact": "Exemple fictif, pas une date réelle à importer.",
  "regions": ["US"],
  "currencies": ["USD"],
  "themes": ["employment"]
}
```

```powershell
python -m tools.bloomberg_watch add outputs/bloomberg_watch/observation.json
```

## Sources du calendrier initial

Les dates ont été vérifiées le 19 octobre 2026 et ne sont pas figées à jamais :
enregistrer les annonces ultérieures de report ou d'horaire comme nouvelles versions.

- [Réserve fédérale](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
- [Bureau of Labor Statistics](https://www.bls.gov/schedule/2026/11_sched.htm)
- [Banque du Japon](https://www.boj.or.jp/en/mopo/mpmsche_minu/)
- [Banque de Corée](https://www.bok.or.kr/eng/main/contents.do?menuNo=400020)

Le premier relevé Bloomberg est un résumé propre de la version mise à jour du
[point de marché du 19 octobre](https://www.bloomberg.com/news/articles/2026-10-18/stock-market-today-dow-s-p-live-updates),
consultée dans le navigateur connecté. Les contenus et déclarations privés ne sont
pas inclus dans cette branche Git.
