"""Append-only, hash-chained local observations. No network or trading code."""

import hashlib
import json
import math
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

KINDS = {"calendar", "release", "news", "analysis"}
FIELDS = {
    "entity_id",
    "kind",
    "title",
    "source_url",
    "source_access",
    "source_published_at",
    "source_version",
    "event_date",
    "event_at",
    "event_timezone",
    "fact",
    "interpretation",
    "regions",
    "currencies",
    "themes",
    "tickers",
    "unit",
    "actual",
    "consensus",
    "consensus_ref",
    "previous_value",
    "revised_previous",
}


def stamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Un horodatage doit inclure son fuseau (+02:00, Z...).")
    return parsed.astimezone(UTC)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def checksum(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate(data, now):
    if not isinstance(data, dict) or set(data) - FIELDS:
        raise ValueError("Champs non reconnus ; l'heure de collecte est attribuée par l'outil.")
    item = dict(data)
    for field in ("entity_id", "kind", "title", "source_url", "source_access"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"Champ obligatoire : {field}.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", item["entity_id"]):
        raise ValueError("Identifiant d'événement invalide.")
    if item["kind"] not in KINDS or item["source_access"] not in {
        "read_full",
        "headline_only",
        "unavailable",
    }:
        raise ValueError("Type d'observation ou niveau de lecture invalide.")
    source = urlsplit(item["source_url"])
    if source.scheme != "https" or not source.hostname or source.username or source.password:
        raise ValueError("URL HTTPS sans identifiants requise.")
    if any(
        re.search(r"token|password|secret|api.?key|session|auth", key, re.I)
        for key, _ in parse_qsl(source.query)
    ):
        raise ValueError("Ne pas enregistrer d'URL contenant un secret ou une session.")
    item["source_url"] = source._replace(fragment="").geturl()
    for field, maximum in (("title", 240), ("fact", 1600), ("interpretation", 1000)):
        text = item.get(field, "") or ""
        if not isinstance(text, str) or len(text) > maximum:
            raise ValueError(f"{field} : note courte requise, pas un article intégral.")
        item[field] = text.strip()
    if item.get("source_published_at"):
        published = stamp(item["source_published_at"])
        if published > now:
            raise ValueError("La version source ne peut pas venir du futur.")
        item["source_published_at"] = published.isoformat()
    else:
        item["source_published_at"] = None
    if item.get("source_version", "unknown") not in {"published", "updated", "unknown"}:
        raise ValueError("Préciser publication initiale, mise à jour ou heure inconnue.")
    item.setdefault("source_version", "unknown")
    if item.get("event_date"):
        item["event_date"] = date.fromisoformat(item["event_date"]).isoformat()
    if item.get("event_at"):
        event = stamp(item["event_at"])
        zone = ZoneInfo(item["event_timezone"])
        day = event.astimezone(zone).date().isoformat()
        if item.get("event_date") and item["event_date"] != day:
            raise ValueError("La date et l'heure de l'événement ne concordent pas.")
        item["event_at"], item["event_date"] = event.isoformat(), day
    if item["kind"] == "calendar" and not item.get("event_date"):
        raise ValueError(
            "Un événement de calendrier exige une date ; l'heure peut rester inconnue."
        )
    for field in ("regions", "currencies", "themes", "tickers"):
        tags = item.get(field, [])
        if not isinstance(tags, list) or any(not isinstance(v, str) or not v.strip() for v in tags):
            raise ValueError(f"{field} : liste de libellés non vides requise.")
        item[field] = sorted(set(v.strip() for v in tags))
    for field in ("actual", "consensus", "previous_value", "revised_previous"):
        value = item.get(field)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Nombre fini requis : {field}.")
    if any(item.get(key) is not None for key in ("actual", "consensus")) and not item.get("unit"):
        raise ValueError("L'unité est obligatoire pour une valeur ou un consensus.")
    if item.get("consensus") is not None and item["kind"] != "calendar":
        raise ValueError("Le consensus est archivé avant publication dans une entrée calendrier.")
    if item.get("actual") is not None and item["kind"] != "release":
        raise ValueError("Seule une publication constatée peut contenir un chiffre réalisé.")
    if item["kind"] == "release":
        if item.get("actual") is None or item["source_access"] != "read_full":
            raise ValueError("Publication : chiffre et lecture effective de la source requis.")
        if item.get("event_at") and stamp(item["event_at"]) > now:
            raise ValueError("Un chiffre réalisé ne peut précéder l'événement.")
        if item.get("event_date") and date.fromisoformat(item["event_date"]) > now.date():
            raise ValueError("Un chiffre réalisé ne peut être daté du futur.")
    return item


class Journal:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.path = self.workspace / "observations.jsonl"

    def read(self):
        if not self.path.exists():
            return []
        rows, previous = [], "0" * 64
        for number, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            row = json.loads(raw)
            body = {key: value for key, value in row.items() if key != "hash"}
            if (
                row.get("seq") != number
                or row.get("previous_hash") != previous
                or row.get("hash") != checksum(body)
            ):
                raise ValueError(f"Journal altéré ou incomplet à la ligne {number}.")
            if rows and stamp(row["recorded_at"]) < stamp(rows[-1]["recorded_at"]):
                raise ValueError("Horloge de collecte non monotone.")
            previous = row["hash"]
            rows.append(row)
        return rows

    def append(self, data, *, _now=None):
        # _now is for synthetic tests only, absent from the CLI and the web form.
        now = _now or datetime.now(UTC)
        lock = self.workspace / ".journal.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError("Journal occupé ; ne pas supprimer son verrou sans contrôle.") from exc
        try:
            os.close(descriptor)
            rows = self.read()
            if rows and now < stamp(rows[-1]["recorded_at"]):
                raise ValueError("Horloge de collecte en recul.")
            item = validate(data, now)
            body = {
                "seq": len(rows) + 1,
                "recorded_at": now.isoformat(),
                "previous_hash": rows[-1]["hash"] if rows else "0" * 64,
                "data": item,
            }
            row = {**body, "hash": checksum(body)}
            # A repeated import does not create a fresh observation or move its first-seen time.
            for existing in rows:
                if canonical(existing["data"]) == canonical(item):
                    return existing
            with self.path.open("ab") as handle:
                handle.write(canonical(row) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            return row
        finally:
            lock.unlink(missing_ok=True)


def visible(rows, as_of):
    limit = stamp(as_of)
    return [
        row
        for row in rows
        if stamp(row["recorded_at"]) <= limit
        and (
            not row["data"].get("source_published_at")
            or stamp(row["data"]["source_published_at"]) <= limit
        )
    ]


def surprise(row, history):
    data = row["data"]
    if data["kind"] != "release":
        return None, "sans objet"
    references = {entry["hash"]: entry for entry in history}
    reference = references.get(data.get("consensus_ref"))
    if reference is None or not data.get("source_published_at"):
        return None, "consensus antérieur ou heure de publication indisponible"
    before, published = stamp(reference["recorded_at"]), stamp(data["source_published_at"])
    prior = reference["data"]
    valid = (
        prior["kind"] == "calendar"
        and prior["entity_id"] == data["entity_id"]
        and prior.get("event_date") == data.get("event_date")
        and data.get("event_date") is not None
        and prior.get("unit") == data.get("unit")
        and prior.get("consensus") is not None
        and prior["source_access"] == "read_full"
        and before < published
        and before < stamp(row["recorded_at"])
    )
    if not valid:
        return None, "consensus non comparable ou enregistré trop tard"
    return data["actual"] - prior[
        "consensus"
    ], "réalisé moins consensus, sans signe favorable/défavorable"
