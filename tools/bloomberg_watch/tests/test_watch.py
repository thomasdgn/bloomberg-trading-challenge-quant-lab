"""Synthetic-only integrity, chronology, reporting and local form tests."""

import json
import threading
from datetime import timedelta
from http.client import HTTPConnection
from http.server import HTTPServer
from urllib.parse import urlencode

import pytest

from tools.bloomberg_watch.__main__ import handler_factory
from tools.bloomberg_watch.journal import Journal, stamp, surprise, validate
from tools.bloomberg_watch.report import export_report, html, snapshot

T0 = stamp("2026-10-15T10:00:00Z")


def entry(**kwargs):
    return {
        "entity_id": "synthetic-news",
        "kind": "news",
        "title": "Synthetic fixture",
        "source_url": "https://www.bloomberg.com/synthetic-fixture",
        "source_access": "read_full",
        "fact": "Synthetic fact, not real market data.",
        "source_published_at": "2026-10-15T09:00:00Z",
        **kwargs,
    }


def test_integrity_and_truncation_of_corrections(tmp_path):
    journal = Journal(tmp_path)
    first = journal.append(entry(), _now=T0)
    before = snapshot(journal.read(), T0.isoformat())
    journal.append(entry(fact="Corrected synthetic fact"), _now=T0 + timedelta(hours=2))
    assert snapshot(journal.read(), T0.isoformat()) == before
    assert journal.read()[1]["previous_hash"] == first["hash"]
    text = journal.path.read_text().replace("Corrected synthetic fact", "Tampered synthetic fact")
    journal.path.write_text(text)
    with pytest.raises(ValueError, match="altéré"):
        journal.read()


def test_idempotent_import_preserves_first_capture_time(tmp_path):
    journal = Journal(tmp_path)
    first = journal.append(entry(), _now=T0)
    journal.append(entry(entity_id="other"), _now=T0 + timedelta(minutes=1))
    assert journal.append(entry(), _now=T0 + timedelta(hours=1)) == first
    assert len(journal.read()) == 2


def test_collected_today_cannot_be_used_yesterday(tmp_path):
    journal = Journal(tmp_path)
    journal.append(entry(source_published_at="2020-01-01T10:00:00Z"), _now=T0)
    assert (
        snapshot(journal.read(), (T0 - timedelta(seconds=1)).isoformat())["observations_visible"]
        == 0
    )


@pytest.mark.parametrize(
    "change",
    [
        {"source_published_at": "2026-10-16T10:00:00Z"},
        {"source_published_at": "2026-10-15T09:00:00"},
        {"source_url": "javascript:alert(1)"},
        {"source_url": "https://www.bloomberg.com/test?token=secret"},
        {"source_url": "https://user:secret@www.bloomberg.com/test"},
        {"recorded_at": "2020-01-01T00:00:00Z"},
        {"actual": 2},
        {"kind": "calendar", "event_date": "2026-11-06", "consensus": float("nan"), "unit": "%"},
    ],
)
def test_invalid_or_future_information_rejected(change):
    with pytest.raises(ValueError):
        validate(entry(**change), T0)


def test_consensus_must_precede_publication_and_match_event(tmp_path):
    journal = Journal(tmp_path)
    forecast = journal.append(
        entry(
            entity_id="US-TEST-2026-10",
            kind="calendar",
            event_date="2026-10-16",
            consensus=2.3,
            unit="%",
        ),
        _now=T0,
    )
    release = journal.append(
        entry(
            entity_id="US-TEST-2026-10",
            kind="release",
            event_date="2026-10-16",
            actual=2.5,
            unit="%",
            consensus_ref=forecast["hash"],
            source_published_at="2026-10-16T12:30:00Z",
        ),
        _now=stamp("2026-10-16T12:35:00Z"),
    )
    assert surprise(release, journal.read())[0] == pytest.approx(0.2)
    wrong = {**release, "data": {**release["data"], "unit": "points"}}
    assert surprise(wrong, journal.read())[0] is None
    late = {**forecast, "recorded_at": "2026-10-16T12:31:00Z"}
    assert surprise(release, [late, release])[0] is None
    wrong_date = {**release, "data": {**release["data"], "event_date": "2026-10-15"}}
    assert surprise(wrong_date, journal.read())[0] is None


def test_unknown_event_hour_and_dst_are_not_invented(tmp_path):
    journal = Journal(tmp_path)
    journal.append(entry(kind="calendar", event_date="2026-10-30"), _now=T0)
    journal.append(
        entry(
            entity_id="BLS-TEST",
            kind="calendar",
            event_date="2026-11-06",
            event_at="2026-11-06T08:30:00-05:00",
            event_timezone="America/New_York",
        ),
        _now=T0,
    )
    state = snapshot(journal.read(), T0.isoformat())
    rendered = html(state, "synthetic-token", journal.read())
    assert "heure non confirmée" in rendered
    assert "06/11 14:30 Paris" in rendered


def test_future_watchlist_and_spoofed_domain_not_used(tmp_path):
    journal = Journal(tmp_path)
    journal.append(
        entry(source_url="https://bloomberg.com.example.org/test", currencies=["USD"]), _now=T0
    )
    future = {
        "recorded_at": (T0 + timedelta(days=1)).isoformat(),
        "items": [{"id": "SYNTHETIC", "currencies": ["USD"]}],
    }
    state = snapshot(journal.read(), T0.isoformat(), future)
    assert state["coverage"]["bloomberg_observations"] == 0
    assert state["updates_24h"][0]["related_declared_lines"] == []


def test_html_escapes_article_content_and_report_preserves_inputs(tmp_path):
    journal = Journal(tmp_path / "workspace")
    journal.append(
        entry(title="<script>alert(1)</script>", fact="<img src=x onerror=bad()>"), _now=T0
    )
    state = snapshot(journal.read(), T0.isoformat())
    rendered = html(state, "token", journal.read())
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered
    (journal.workspace / "watchlist.json").write_text(
        json.dumps(
            {
                "recorded_at": (T0 + timedelta(days=1)).isoformat(),
                "items": [{"id": "FUTURE"}],
            }
        )
    )
    report = export_report(journal, tmp_path / "report", T0.isoformat())
    manifest = json.loads((report.parent / "manifest.json").read_text())
    assert manifest["journal_tip"] == journal.read()[-1]["hash"]
    assert (report.parent / "watchlist.json").exists()
    assert json.loads((report.parent / "watchlist.json").read_text()) == {}
    with pytest.raises(FileExistsError):
        export_report(journal, report.parent, T0.isoformat())


def test_loopback_form_origin_and_csrf_gate(tmp_path):
    journal = Journal(tmp_path)
    server = HTTPServer(("127.0.0.1", 0), handler_factory(journal, "synthetic-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        assert response.status == 200 and b"synthetic-token" in response.read()
        body = urlencode({"csrf": "wrong", **entry()})
        connection.request("POST", "/add", body=body, headers={"Origin": origin})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        assert journal.read() == []
        body = urlencode({"csrf": "synthetic-token", **entry()})
        connection.request("POST", "/add", body=body, headers={"Origin": "https://example.org"})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.request("POST", "/add", body=body, headers={"Origin": origin})
        response = connection.getresponse()
        assert response.status == 303
        response.read()
        assert len(journal.read()) == 1
        automatic = entry(entity_id="")
        automatic["source_url"] = "https://www.bloomberg.com/another-synthetic-fixture"
        body = urlencode({"csrf": "synthetic-token", **automatic})
        connection.request("POST", "/add", body=body, headers={"Origin": origin})
        response = connection.getresponse()
        assert response.status == 303
        response.read()
        assert journal.read()[-1]["data"]["entity_id"].startswith("auto-")
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_existing_lock_prevents_concurrent_append_without_deleting_it(tmp_path):
    journal = Journal(tmp_path)
    lock = tmp_path / ".journal.lock"
    lock.write_text("another writer")
    with pytest.raises(ValueError, match="occupé"):
        journal.append(entry(), _now=T0)
    assert lock.read_text() == "another writer" and journal.read() == []
