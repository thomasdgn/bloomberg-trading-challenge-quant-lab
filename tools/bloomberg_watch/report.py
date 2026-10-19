"""Deterministic prospective briefing and a local HTML reading view."""

import hashlib
import json
import platform
from datetime import UTC, date, datetime, timedelta
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from tools.bloomberg_watch.journal import canonical, stamp, surprise, visible

END = date(2026, 11, 13)
PARIS = ZoneInfo("Europe/Paris")
HOLDINGS = {
    "declared_lines_execution_not_reconciled": "exécutions à confirmer",
    "not_supplied": "portefeuille non renseigné",
}
ACCESS = {
    "read_full": "source consultée",
    "headline_only": "titre seulement",
    "unavailable": "source indisponible",
}
VERSIONS = {
    "updated": "mise à jour",
    "published": "publication initiale",
    "unknown": "heure inconnue",
}


def snapshot(rows, as_of, watchlist=None):
    moment = stamp(as_of)
    if watchlist and watchlist.get("recorded_at") and stamp(watchlist["recorded_at"]) > moment:
        watchlist = {}
    history = visible(rows, as_of)
    latest = {}
    for row in history:
        latest[row["data"]["entity_id"]] = row
    upcoming, updates, overdue = [], [], []
    for row in latest.values():
        item = row["data"]
        related = []
        for asset in (watchlist or {}).get("items", []):
            direct = asset["id"] in item["tickers"]
            tags = set(item["currencies"]) & set(asset.get("currencies", []))
            topics = set(item["themes"]) & set(asset.get("themes", []))
            if direct or tags or topics:
                related.append(asset["id"])
        entry = {
            **row,
            "related_declared_lines": sorted(related),
            "surprise": surprise(row, history)[0],
            "surprise_status": surprise(row, history)[1],
        }
        if item["kind"] == "calendar":
            event_day = date.fromisoformat(item["event_date"])
            if moment.astimezone(PARIS).date() <= event_day <= END:
                upcoming.append(entry)
            elif event_day < moment.astimezone(PARIS).date():
                overdue.append(entry)
        elif stamp(row["recorded_at"]) >= moment - timedelta(hours=24):
            updates.append(entry)
    upcoming.sort(key=lambda row: (row["data"]["event_date"], row["data"].get("event_at") or ""))
    updates.sort(key=lambda row: row["recorded_at"], reverse=True)
    return {
        "as_of": moment.isoformat(),
        "horizon_end": END.isoformat(),
        "observations_visible": len(history),
        "journal_tip": history[-1]["hash"] if history else None,
        "watchlist_sha256": hashlib.sha256(canonical(watchlist or {})).hexdigest(),
        "holdings_status": (watchlist or {}).get("status", "not_supplied"),
        "upcoming": upcoming,
        "updates_24h": updates,
        "overdue_unconfirmed": overdue,
        "coverage": {
            "bloomberg_observations": sum(
                (
                    urlsplit(row["data"]["source_url"]).hostname == "bloomberg.com"
                    or (urlsplit(row["data"]["source_url"]).hostname or "").endswith(
                        ".bloomberg.com"
                    )
                )
                and row["data"]["source_access"] == "read_full"
                for row in history
            ),
            "limited_access_observations": sum(
                row["data"]["source_access"] != "read_full" for row in history
            ),
            "warning": "Une absence dans ce journal ne signifie pas absence d'événement. "
            "Couverture partielle ; sources officielles identifiées séparément.",
        },
    }


def event_time(data):
    if data.get("event_at"):
        paris = stamp(data["event_at"]).astimezone(PARIS)
        return paris.strftime("%d/%m %H:%M") + " Paris"
    return data["event_date"] + " — heure non confirmée"


def markdown(state):
    lines = [
        "# Veille macro prospective — Bloomberg et sources officielles",
        f"Arrêté au {stamp(state['as_of']).astimezone(PARIS).isoformat()}. "
        f"Horizon : {state['horizon_end']}. Portefeuille : "
        f"{HOLDINGS.get(state['holdings_status'], state['holdings_status'])}.",
        "Journal d'information, sans signal de portefeuille, ordre ou estimation de rendement.",
        "## Faits nouveaux et publications — dernières 24 h",
    ]
    if not state["updates_24h"]:
        lines.append(
            "Aucune nouvelle observation enregistrée ; cela ne prouve pas l'absence de nouvelles."
        )
    for row in state["updates_24h"]:
        item = row["data"]
        lines += [
            f"### {item['title']}",
            item["fact"] or "Fait non renseigné.",
            f"Source : [consulter]({item['source_url']}) — {ACCESS[item['source_access']]}. "
            f"Version source : {item.get('source_published_at') or 'heure inconnue'}, "
            f"{VERSIONS[item['source_version']]}. Collecte : {row['recorded_at']}.",
        ]
        if item["interpretation"]:
            lines.append("**Interprétation distincte, à discuter :** " + item["interpretation"])
        if item["kind"] == "release":
            lines.append(
                f"Réalisé : {item['actual']} {item.get('unit', '')}. "
                f"Surprise brute : {row['surprise']} ({row['surprise_status']})."
            )
            if item.get("previous_value") is not None and item.get("revised_previous") is not None:
                delta = item["revised_previous"] - item["previous_value"]
                lines.append(
                    f"Précédent déclaré : {item['previous_value']} ; précédent révisé : "
                    f"{item['revised_previous']} ; révision brute : {delta}."
                )
        lines.append(
            "Lignes déclarées liées par identifiant/devise/thème : "
            + (", ".join(row["related_declared_lines"]) or "correspondance non établie")
            + ". Ce lien ne mesure ni poids ni risque ; exécutions non présumées."
        )
    lines += ["## Calendrier connu jusqu'au 13 novembre"]
    for row in state["upcoming"]:
        item = row["data"]
        lines.append(
            f"- {event_time(item)} — {item['title']} — {item['source_url']} "
            f"({ACCESS[item['source_access']]})."
        )
    if not state["upcoming"]:
        lines.append("Calendrier non renseigné pour cette fenêtre.")
    if state["overdue_unconfirmed"]:
        lines += ["## Publications passées sans mise à jour enregistrée"]
        lines += [
            f"- {row['data']['event_date']} — {row['data']['title']} : à vérifier."
            for row in state["overdue_unconfirmed"]
        ]
    lines += [
        "## Couverture et traçabilité",
        state["coverage"]["warning"],
        f"{state['observations_visible']} observations ; "
        f"sources Bloomberg consultées : {state['coverage']['bloomberg_observations']} ; "
        f"{state['coverage']['limited_access_observations']} lectures partielles/indisponibles.",
        "Les prévisions et avis restent distincts des publications. Les valeurs ne sont pas "
        "injectées dans macro_engine et ne changent ni son cache ni ses paramètres. "
        "Les observations ne deviennent utilisables qu'à leur enregistrement dans ce journal.",
        f"Empreinte de fin de journal : {state['journal_tip'] or 'vide'}. "
        f"Empreinte liste de suivi : {state['watchlist_sha256']}.",
    ]
    return "\n\n".join(lines) + "\n"


STYLE = """
body{font:16px system-ui,sans-serif;margin:0;background:#f3f5f7;color:#182335}
header{background:#16283d;color:white;padding:28px max(5vw,20px)}
main{max-width:1080px;margin:28px auto;padding:0 20px}h1{font-size:28px;margin:0 0 8px}
section{background:white;border:1px solid #dae1e8;border-radius:12px;padding:22px;margin:18px 0}
label{display:block;margin:12px 0 5px;font-weight:600}input,select,textarea{font:inherit;
box-sizing:border-box;width:100%;padding:10px;border:1px solid #acb8c6;border-radius:6px}
textarea{min-height:85px}button{background:#176b65;color:white;padding:12px 20px;border:0;
border-radius:6px;font:inherit;cursor:pointer;margin:18px 0}a{color:#176b65;overflow-wrap:anywhere}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:0 22px}
.badge{background:#e8f1f2;padding:6px 10px;border-radius:6px;display:inline-block;margin:4px}
.muted{color:#5d6d80}small{display:block;color:#5d6d80}
article{border-top:1px solid #ddd;padding:12px 0}
.notice{border-left:4px solid #d99a24;padding:12px;background:#fff6e4}details{margin:16px 0}
"""


def html(state, token, references):
    def esc(value):
        return escape(str(value), quote=True)

    cards = []
    for row in state["updates_24h"]:
        item = row["data"]
        linked = ", ".join(row["related_declared_lines"]) or "correspondance non établie"
        source_time = (
            stamp(item["source_published_at"]).astimezone(PARIS).strftime("%d/%m/%Y %H:%M Paris")
            if item.get("source_published_at")
            else "heure inconnue"
        )
        capture_time = stamp(row["recorded_at"]).astimezone(PARIS).strftime("%d/%m/%Y %H:%M Paris")
        cards.append(
            f"<article><h3>{esc(item['title'])}</h3><p>{esc(item['fact'])}</p>"
            f"<p class='muted'>Interprétation : {esc(item['interpretation'] or 'non ajoutée')}</p>"
            f"<a href='{esc(item['source_url'])}' rel='noreferrer' target='_blank'>Source</a>"
            f"<small>Version source : {esc(source_time)} · Collecte : {esc(capture_time)}</small>"
            f"<p class='muted'>Liens thématiques déclarés : {esc(linked)}. "
            "Poids et risque non calculés.</p></article>"
        )
    calendar = "".join(
        f"<article><b>{esc(event_time(row['data']))}</b> — {esc(row['data']['title'])} "
        f"<a href='{esc(row['data']['source_url'])}' rel='noreferrer' "
        "target='_blank'>Source</a></article>"
        for row in state["upcoming"]
    )
    options = "<option value=''>Aucun consensus archivé</option>" + "".join(
        f"<option value='{row['hash']}'>{esc(row['data']['title'])} — "
        f"{esc(row['data'].get('consensus'))} {esc(row['data'].get('unit', ''))}</option>"
        for row in references
        if row["data"]["kind"] == "calendar" and row["data"].get("consensus") is not None
    )
    template = Template((Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8"))
    return template.substitute(
        style=STYLE,
        count=state["observations_visible"],
        bloomberg_count=state["coverage"]["bloomberg_observations"],
        holdings=esc(
            {
                "declared_lines_execution_not_reconciled": "Exécutions à confirmer",
                "not_supplied": "Portefeuille non renseigné",
            }.get(state["holdings_status"], state["holdings_status"])
        ),
        cards="".join(cards) or "<p>Aucune observation nouvelle enregistrée.</p>",
        calendar=calendar or "<p>Calendrier non renseigné.</p>",
        warning=esc(state["coverage"]["warning"]),
        token=esc(token),
        options=options,
    )


def export_report(journal, destination, as_of=None):
    as_of = as_of or datetime.now(UTC).isoformat()
    watch_path = journal.workspace / "watchlist.json"
    watch = json.loads(watch_path.read_text(encoding="utf-8")) if watch_path.exists() else {}
    if watch.get("recorded_at") and stamp(watch["recorded_at"]) > stamp(as_of):
        watch = {}
    state = snapshot(journal.read(), as_of, watch)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "RAPPORT.md").write_text(markdown(state), encoding="utf-8")
    (destination / "snapshot.json").write_bytes(canonical(state) + b"\n")
    (destination / "watchlist.json").write_bytes(canonical(watch) + b"\n")
    manifest = {
        "as_of": state["as_of"],
        "journal_tip": state["journal_tip"],
        "watchlist_sha256": state["watchlist_sha256"],
        "python_version": platform.python_version(),
        "code_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.iterdir())
            if path.suffix in {".py", ".html"}
        },
        "files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(destination.iterdir())
        },
    }
    (destination / "manifest.json").write_bytes(canonical(manifest) + b"\n")
    return destination / "RAPPORT.md"
