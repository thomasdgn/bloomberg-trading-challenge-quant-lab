"""Local-only interface and commands for a human-reviewed Bloomberg watch."""

import argparse
import hmac
import json
import secrets
from datetime import UTC, datetime
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tools.bloomberg_watch.journal import Journal, canonical, checksum, stamp
from tools.bloomberg_watch.report import export_report, html, markdown, snapshot

ROOT = Path(__file__).resolve().parents[2]


def workspace_path(value):
    path = Path(value).resolve()
    if not path.is_relative_to((ROOT / "outputs").resolve()):
        raise ValueError("Le journal privé doit rester sous outputs/, ignoré par Git.")
    return path


def read_watchlist(workspace):
    path = workspace / "watchlist.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def handler_factory(journal, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No private notes or source URLs in access logs.

        def send_body(self, body, content_type="text/html; charset=utf-8", status=200):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(encoded)

        def valid_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.valid_host():
                self.send_body("Hôte refusé.", status=403)
                return
            try:
                route = urlsplit(self.path).path
                rows = journal.read()
                state = snapshot(
                    rows, datetime.now(UTC).isoformat(), read_watchlist(journal.workspace)
                )
                if route == "/":
                    self.send_body(html(state, token, rows))
                elif route == "/report":
                    self.send_body(markdown(state), "text/plain; charset=utf-8")
                else:
                    self.send_body("Page inconnue.", status=404)
            except (ValueError, KeyError, OSError) as exc:
                self.send_body(escape(str(exc)), status=400)

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.valid_host() or self.headers.get("Origin") != origin:
                self.send_body("Origine refusée.", status=403)
                return
            if self.path != "/add":
                self.send_body("Route inconnue.", status=404)
                return
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 32768:
                    raise ValueError("Formulaire trop volumineux ou vide.")
                fields = parse_qs(self.rfile.read(size).decode("utf-8"), keep_blank_values=False)
                supplied = fields.pop("csrf", [""])[0]
                if not hmac.compare_digest(supplied, token):
                    self.send_body("Jeton de formulaire invalide.", status=403)
                    return
                data = {
                    key: values[0].strip() for key, values in fields.items() if values[0].strip()
                }
                if not data.get("entity_id"):
                    history = journal.read()
                    reference = next(
                        (row for row in history if row["hash"] == data.get("consensus_ref")), None
                    )
                    if reference is not None:
                        data["entity_id"] = reference["data"]["entity_id"]
                    else:
                        identity = [data.get("source_url")]
                        if data.get("kind") in {"calendar", "release"}:
                            identity += [data.get("event_date"), data.get("title")]
                        data["entity_id"] = "auto-" + checksum(identity)[:20]
                for field in ("regions", "currencies", "themes", "tickers"):
                    data[field] = [v.strip() for v in data.get(field, "").split(",") if v.strip()]
                for field in ("actual", "consensus", "previous_value", "revised_previous"):
                    if field in data:
                        data[field] = float(data[field])
                journal.append(data)
                self.send_response(303)
                self.send_header("Location", "/?saved=1")
                self.end_headers()
            except (ValueError, KeyError, OSError) as exc:
                self.send_body(
                    "<h1>Observation non enregistrée</h1><p>"
                    + escape(str(exc))
                    + "</p><a href='/'>Retour au formulaire</a>",
                    status=400,
                )

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default="outputs/bloomberg_watch")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--watchlist", type=Path)
    add = commands.add_parser("add")
    add.add_argument("input", type=Path, help="One observation JSON, not a scraped article.")
    report = commands.add_parser("report")
    report.add_argument("--as-of")
    report.add_argument("--name")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8767)
    args = parser.parse_args(argv)
    try:
        journal = Journal(workspace_path(args.workspace))
        if args.command == "init":
            if args.watchlist:
                destination = journal.workspace / "watchlist.json"
                if destination.exists():
                    raise ValueError(
                        "Une liste de suivi existe déjà ; conserver sa version précédente."
                    )
                watchlist = json.loads(args.watchlist.read_text(encoding="utf-8"))
                watchlist["recorded_at"] = datetime.now(UTC).isoformat()
                destination.write_bytes(canonical(watchlist) + b"\n")
            print(f"Journal prêt : {journal.workspace}")
        elif args.command == "add":
            data = json.loads(args.input.read_text(encoding="utf-8"))
            print(journal.append(data)["hash"])
        elif args.command == "report":
            if args.as_of and stamp(args.as_of) > datetime.now(UTC):
                raise ValueError("Un rapport ne peut pas être arrêté dans le futur.")
            name = args.name or datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            destination = (journal.workspace / "reports" / name).resolve()
            if not destination.is_relative_to((journal.workspace / "reports").resolve()):
                raise ValueError("Nom de rapport invalide.")
            print(export_report(journal, destination, args.as_of))
        else:
            if not 1024 <= args.port <= 65535:
                raise ValueError("Port local invalide.")
            server = HTTPServer(
                ("127.0.0.1", args.port), handler_factory(journal, secrets.token_urlsafe(32))
            )
            print(f"Veille locale : http://127.0.0.1:{args.port}", flush=True)
            server.serve_forever()
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"Erreur : {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
