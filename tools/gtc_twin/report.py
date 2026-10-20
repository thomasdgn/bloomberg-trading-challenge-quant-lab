"""Standalone, no-JavaScript investment research report (safe escaped HTML)."""

from __future__ import annotations

from html import escape
from typing import Any

from tools.gtc_live.ledger import DataBlocked


def _percent(value: float, signed: bool = True) -> str:
    return f"{value:+.2%}" if signed else f"{value:.1%}"


def _bar(percent: float, *, css_class: str = "") -> str:
    amount = max(0.0, min(100.0, percent * 100))
    return (
        f'<div class="meter"><div class="fill {escape(css_class, quote=True)}" '
        f'style="width:{amount:.1f}%"></div></div>'
    )


def render_html(report: dict[str, Any]) -> str:
    """Render an already computed simulation without recomputing any statistic."""
    if not isinstance(report, dict) or report.get("status") != "SIMULATION_ONLY":
        raise DataBlocked("a completed simulation report is required")
    method = report["method"]
    summaries = report["summaries"]
    labels = ("HOLD", "REBALANCE", "DEFENSIVE")
    if set(summaries) != set(labels):
        raise DataBlocked("the three required comparisons are missing")
    all_values = [
        summaries[name][key]
        for name in labels
        for key in ("relative_wealth_p10", "relative_wealth_p90")
    ]
    low, high = min(all_values), max(all_values)
    spread = max(high - low, 1e-9)
    colors = {"HOLD": "#72a6ff", "REBALANCE": "#b69dff", "DEFENSIVE": "#6ee7bd"}
    cards = []
    rows = []
    for name in labels:
        data = summaries[name]
        q10, q50, q90 = (
            data["relative_wealth_p10"],
            data["relative_wealth_median"],
            data["relative_wealth_p90"],
        )
        fraction = data["empirical_fraction_beating_wls"]
        placement = max(0.0, min(100.0, 100 * (q10 - low) / spread))
        width = max(1.0, min(100.0 - placement, 100 * (q90 - q10) / spread))
        center = max(0.0, min(100.0, 100 * (q50 - low) / spread))
        color = colors[name]
        paired = (
            "Baseline comparator"
            if name == "HOLD"
            else (
                "Paired improvement over HOLD: "
                + _percent(data["paired_improvement_over_hold_median"])
                + " median, "
                + _percent(data["paired_improvement_over_hold_p10"])
                + " lower decile"
            )
        )
        cards.append(
            f"""<section class="strategy" style="--tint:{color}">
              <div class="eyebrow">{escape(name)}</div>
              <div class="big">{_percent(q50)}</div>
              <div class="muted">Median WLS-relative terminal wealth</div>
              <div class="divider"></div>
              <div class="mini"><span>Empirical beat frequency</span>
                 <strong>{_percent(fraction, signed=False)}</strong></div>
              {_bar(fraction)}
              <div class="mini"><span>Equity allocation</span>
                 <strong>{_percent(data["equity_weight"], signed=False)}</strong></div>
              <div class="mini"><span>One-way turnover</span>
                 <strong>{_percent(data["one_way_turnover"], signed=False)}</strong></div>
              <p class="detail">{escape(paired)}</p>
            </section>"""
        )
        rows.append(
            f"""<tr><th scope="row">{escape(name)}</th>
                <td>{_percent(q10)}</td><td>{_percent(q50)}</td>
                <td>{_percent(q90)}</td>
                <td>{_percent(data["relative_drawdown_p10"])}</td>
                <td>{_percent(data["one_off_cost_fraction_of_nav"])}</td></tr>"""
        )
        rows.append(
            f"""<tr class="range-row"><td colspan="6">
            <div class="range-track"><div class="range"
              style="left:{placement:.1f}%;width:{width:.1f}%;background:{color}"></div>
              <div class="dot" style="left:{center:.1f}%;background:{color}"></div>
            </div></td></tr>"""
        )
    disclaimer = "".join("<li>" + escape(str(text)) + "</li>" for text in report["disclosures"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GTC Digital Twin — {escape(str(report["run_id"]))}</title>
<style>
:root {{ color-scheme:dark; --bg:#0c1222; --panel:#151f35; --text:#eff6ff;
--muted:#a7b6cf; --line:#303e58; }}
* {{box-sizing:border-box}}
body {{margin:0;background:radial-gradient(ellipse at top,#1e3153 0%,var(--bg) 65%);
color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif}}
main {{max-width:1160px;margin:auto;padding:38px 22px 64px}}
h1 {{font-size:clamp(31px,4.1vw,54px);letter-spacing:-.045em;margin:12px 0}}
h2 {{font-size:21px;letter-spacing:-.02em;margin:34px 0 14px}}
p {{line-height:1.62}}
.flag {{display:inline-block;border:1px solid #fecaca;color:#fecaca;
border-radius:30px;padding:7px 12px;font-weight:700;font-size:11px;letter-spacing:.08em}}
.subtitle,.muted,.detail {{color:var(--muted)}}
.subtitle {{max-width:760px;font-size:16px}}
.grid {{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:26px 0}}
.strategy,.panel {{background:rgba(21,31,53,.92);border:1px solid var(--line);
border-radius:18px;padding:22px}}
.strategy {{border-top:3px solid var(--tint);min-height:290px}}
.eyebrow {{font-size:12px;letter-spacing:.14em;font-weight:800;color:var(--tint)}}
.big {{font-size:36px;letter-spacing:-.05em;font-weight:750;margin:12px 0 2px}}
.divider {{border-top:1px solid var(--line);margin:18px 0}}
.mini {{display:flex;justify-content:space-between;gap:8px;font-size:13px;margin:9px 0}}
.mini span {{color:var(--muted)}}
.meter {{height:7px;background:#283753;border-radius:10px;overflow:hidden;margin:7px 0 18px}}
.fill {{height:100%;background:var(--tint,#72a6ff);border-radius:10px}}
.detail {{font-size:12px;line-height:1.55}}
table {{width:100%;border-collapse:collapse;text-align:right;font-size:13px}}
th,td {{padding:13px 8px;border-bottom:1px solid #2d3a50}}
thead th {{color:var(--muted);font-weight:600}}
th:first-child,td:first-child {{text-align:left}}
.range-row td {{padding:0 8px 13px;border-bottom:1px solid #4a5b76}}
.range-track {{height:16px;background:#222f47;border-radius:8px;position:relative}}
.range {{position:absolute;top:6px;height:5px;border-radius:12px}}
.dot {{position:absolute;top:2px;width:5px;height:13px;border-radius:4px}}
.meta {{display:flex;flex-wrap:wrap;gap:10px;margin:24px 0}}
.meta span {{border-radius:9px;background:#23314d;padding:10px 12px;font-size:12px}}
li {{line-height:1.7;color:var(--muted);padding-bottom:6px}}
strong {{font-variant-numeric:tabular-nums}}
code {{overflow-wrap:anywhere;color:#b9cfff}}
footer {{margin-top:36px;font-size:12px;color:var(--muted)}}
@media(max-width:790px) {{.grid{{grid-template-columns:1fr}}
table{{font-size:11px}}th,td{{padding:9px 4px}}}}
</style></head><body><main>
<span class="flag">RESEARCH ONLY · NOT A TRADING SIGNAL</span>
<h1>GTC Digital Twin <span style="color:#6ee7bd">/</span> Decision Lab</h1>
<p class="subtitle">Three counterfactual portfolios, identical resampled market paths.
Compare HOLD, a manually supplied REBALANCE, and a lower-equity DEFENSIVE scenario
through the challenge deadline. No automatic orders.</p>
<div class="meta">
<span>Decision: {escape(str(method["decision_date"]))}</span>
<span>Competition ends: {escape(str(method["competition_end"]))}</span>
<span>{int(method["horizon_sessions"])} sessions left</span>
<span>{int(method["paths"]):,} historical resamples</span>
<span>Block: {int(method["block_size_sessions"])} sessions</span>
</div>
<div class="grid">{"".join(cards)}</div>
<h2>Distribution of relative wealth vs. WLS</h2>
<section class="panel"><p class="muted">10th–90th percentile band (median marker).
Values are price-return-only, after illustrative initial transaction costs.</p>
<table><thead><tr><th>Strategy</th><th>10th percentile</th><th>Median</th>
<th>90th percentile</th><th>10th pct drawdown</th><th>Cost / NAV</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></section>
<h2>Data lineage & reproducibility</h2>
<section class="panel">
<p>Input SHA-256: <code>{escape(str(report["input_sha256"]))}</code></p>
<p>Run identifier: <code>{escape(str(report["run_id"]))}</code></p>
<p class="muted">History: {escape(str(method["history_start"]))} to
{escape(str(method["history_end"]))} · {int(method["observed_history_rows"])} aligned days ·
seed {int(method["seed"])} · source: {escape(str(method["source"]))}</p>
</section>
<h2>What this does NOT prove</h2><section class="panel"><ul>{disclaimer}</ul></section>
<footer>© Competition research sandbox · Standalone offline HTML · No brokerage integration</footer>
</main></body></html>"""
