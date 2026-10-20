"""Self-contained HTML and sanitized report checks."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.gtc_live.ledger import DataBlocked
from tools.gtc_twin.engine import simulate
from tools.gtc_twin.report import render_html


def test_report_is_standalone_and_contains_all_scenarios(example_payload) -> None:
    result = simulate(example_payload)
    html = render_html(result)
    assert "<!doctype html>" in html
    assert "HOLD" in html
    assert "REBALANCE" in html
    assert "DEFENSIVE" in html
    assert "NO" not in result["status"]  # clearly simulation-only state
    assert result["run_id"] in html
    assert "calibrated probabilities" in html.lower() or "NOT calibrated" in html
    assert "<script" not in html.lower()
    assert "src=\"http" not in html


def test_input_provenance_cannot_inject_html(example_payload) -> None:
    source = deepcopy(example_payload)
    source["data_verification"]["source"] = '<script>alert("bad")</script>'
    html = render_html(simulate(source))
    assert '<script>alert("bad")</script>' not in html
    assert "&lt;script&gt;" in html


def test_broken_result_is_rejected(example_payload) -> None:
    report = simulate(example_payload)
    del report["summaries"]["HOLD"]
    with pytest.raises(DataBlocked):
        render_html(report)
