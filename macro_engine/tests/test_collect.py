"""Collection boundary tests; the state/analogue truncation test comes later."""

import io
import json
from datetime import UTC, datetime

import pandas as pd
import pytest
import requests

from macro_engine import config as cfg
from macro_engine.collect import (
    CacheRun,
    CollectionError,
    Collector,
    observations_frame,
    parse_epu,
    parse_fred_records,
    parse_gpr,
)


@pytest.fixture
def cache(tmp_path):
    return CacheRun(tmp_path, datetime(2026, 10, 18, tzinfo=UTC))


def test_existing_raw_cache_cannot_be_overwritten_or_escaped(cache):
    path = cache.write_bytes("raw.json", b"original")
    with pytest.raises(FileExistsError):
        cache.write_bytes("raw.json", b"changed")
    with pytest.raises(CollectionError):
        cache.write_bytes("../outside.json", b"outside")
    assert path.read_bytes() == b"original"


def test_fred_missing_values_remain_missing_without_fill():
    frame = parse_fred_records(
        [
            {"date": "2020-01-01", "value": "2"},
            {"date": "2020-01-02", "value": "."},
            {"date": "2020-01-03", "value": "4"},
        ]
    )
    assert frame["value"].iloc[0] == 2
    assert pd.isna(frame["value"].iloc[1])
    assert frame["value"].iloc[-1] == 4
    assert len(frame) == 3


def test_alfred_preserves_both_revision_values_and_validity_endpoints():
    frame = parse_fred_records(
        [
            {
                "date": "2020-01-01",
                "value": "3.6",
                "realtime_start": "2020-02-07",
                "realtime_end": "2020-03-05",
            },
            {
                "date": "2020-01-01",
                "value": "3.5",
                "realtime_start": "2020-03-06",
                "realtime_end": "9999-12-31",
            },
        ],
        vintages=True,
    )
    assert frame["value"].tolist() == [3.6, 3.5]
    assert frame["realtime_start"].tolist() == ["2020-02-07", "2020-03-06"]
    assert frame["realtime_end"].tolist()[-1] == "9999-12-31"


def test_repeated_observation_key_is_rejected():
    with pytest.raises(CollectionError, match="Duplicate"):
        observations_frame(["2020-01-01", "2020-01-01"], [1, 2])


def test_epu_uses_news_column_and_does_not_join_pre_1985_methodology():
    source = pd.DataFrame(
        {
            "Year": [1984, 1985, 1985],
            "Month": [12, 1, 2],
            "News_Based_Policy_Uncert_Index": [900, 100, 110],
            "Three_Component_Index": [800, 200, 210],
        }
    )
    output = io.BytesIO()
    source.to_excel(output, index=False, sheet_name=cfg.EPU_SHEET_NAME)
    frame = parse_epu(output.getvalue())
    assert frame["value"].tolist() == [100, 110]
    assert frame["date"].min() == pd.Timestamp("1985-01-01")


def test_epu_credit_is_not_an_observation_but_bad_data_is_never_dropped():
    raw = pd.DataFrame(
        {
            "Year": [1985, cfg.EPU_CREDIT_PREFIX + " (attribution)"],
            "Month": [1, None],
            "News_Based_Policy_Uncert_Index": [100, None],
        }
    )
    output = io.BytesIO()
    raw.to_excel(output, index=False, sheet_name=cfg.EPU_SHEET_NAME)
    frame = parse_epu(output.getvalue())
    assert frame["value"].tolist() == [100]
    assert frame.attrs["publisher_credit_rows"] == 1
    raw.loc[1, "Year"] = "unrecognized malformed row"
    output = io.BytesIO()
    raw.to_excel(output, index=False, sheet_name=cfg.EPU_SHEET_NAME)
    with pytest.raises(ValueError):
        parse_epu(output.getvalue())


def test_gpr_never_substitutes_historical_or_old_index(monkeypatch):
    raw = pd.DataFrame({"month": pd.to_datetime(["1985-01-01"]), "GPRH": [200], "GPR_OLD": [300]})
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: raw)
    with pytest.raises(CollectionError, match="reference GPR"):
        parse_gpr(b"synthetic workbook stub")


class Response:
    ok = True
    status_code = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, content):
        self.content = content


class Session:
    def __init__(self, responses):
        self.headers = {}
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


def test_api_key_is_not_written_in_request_metadata_or_transport_errors(cache, monkeypatch):
    secret = "synthetic-do-not-persist"
    monkeypatch.setenv(cfg.FRED_API_KEY_ENV, secret)
    session = Session([Response(b'{"data": []}'), requests.ConnectionError(secret)])
    collector = Collector(cache, session)
    collector._get("https://example.test", "safe", "json", {"api_key": secret, "id": "X"})
    for path in cache.root.iterdir():
        assert secret.encode() not in path.read_bytes()
    with pytest.raises(CollectionError) as failure:
        collector._get("https://example.test", "error", "json", {"api_key": secret})
    assert secret not in str(failure.value)
    assert (
        "api_key"
        not in json.loads((cache.root / "safe.metadata.json").read_text())["request_parameters"]
    )


def test_response_echoing_api_key_is_never_cached(cache, monkeypatch):
    monkeypatch.setenv(cfg.FRED_API_KEY_ENV, "synthetic-key")
    collector = Collector(cache, Session([Response(b"synthetic-key")]))
    with pytest.raises(CollectionError, match="credential"):
        collector._get("https://example.test", "unsafe", "json")
    assert not list(cache.root.iterdir())


def test_fred_pagination_collects_all_rows_and_offsets(cache, monkeypatch):
    monkeypatch.setenv(cfg.FRED_API_KEY_ENV, "synthetic-key")
    pages = [
        {"count": 3, "observations": [{"date": "2020-01-01"}, {"date": "2020-01-02"}]},
        {"count": 3, "observations": [{"date": "2020-01-03"}]},
    ]
    session = Session([Response(json.dumps(page).encode()) for page in pages])
    collector = Collector(cache, session)
    rows, count = collector._fred_pages("series/observations", "X", "observations", {})
    assert len(rows) == count == 3
    assert [call[1]["offset"] for call in session.calls] == [0, 2]


def test_fred_truncated_page_is_not_reported_as_complete(cache, monkeypatch):
    monkeypatch.setenv(cfg.FRED_API_KEY_ENV, "synthetic-key")
    collector = Collector(
        cache, Session([Response(json.dumps({"count": 1, "observations": []}).encode())])
    )
    with pytest.raises(CollectionError, match="truncated"):
        collector._fred_pages("series/observations", "X", "observations", {})


def test_current_and_alfred_requests_never_share_a_cache_filename(cache, monkeypatch):
    monkeypatch.setenv(cfg.FRED_API_KEY_ENV, "synthetic-key")
    pages = [
        {"count": 1, "observations": [{"date": "2020-01-01", "value": "3.5"}]},
        {"count": 2, "vintage_dates": ["2020-02-07", "2020-03-06"]},
        {
            "count": 2,
            "observations": [
                {
                    "date": "2020-01-01",
                    "value": "3.6",
                    "realtime_start": "2020-02-07",
                    "realtime_end": "2020-03-05",
                },
                {
                    "date": "2020-01-01",
                    "value": "3.5",
                    "realtime_start": "2020-03-06",
                    "realtime_end": "9999-12-31",
                },
            ],
        },
    ]
    collector = Collector(cache, Session([Response(json.dumps(p).encode()) for p in pages]))
    spec = next(s for s in cfg.SERIES if s.identifier == "UNRATE")
    row = collector.collect_one(spec, None)
    assert row["collection_status"] == "collected"
    assert row["vintage_count"] == 2
    assert row["vintage_observation_rows"] == 2
    assert row["alfred_status"] == "collected"
    assert row["pit_status"] == "PIT_VERIFIED"
    assert len(collector.artifacts) == 3
    assert len({artifact["file"] for artifact in collector.artifacts}) == 3
