"""Self-contained offline Plotly diagnostics; no portfolio/performance analysis."""

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from macro_engine import config as cfg


def render_diagnostics(reference, runs, registry: pd.DataFrame) -> str:
    sections = [
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Macro — qualité et analogues</title>",
        "<style>body{font-family:system-ui;margin:2rem auto;max-width:1400px;"
        "padding:0 1rem}table{border-collapse:collapse;font-size:.85rem}"
        "th,td{padding:.4rem;border:1px solid #ccc}section{margin:2rem 0}"
        ".scroll{overflow:auto}h1,h2{line-height:1.3}</style></head><body>",
        f"<h1>Diagnostic macro au {runs[0].state.query_date.date()}</h1>",
        f"<p>Cache unique : {escape(cfg.REFERENCE_CACHE)}. "
        f"Échantillon {runs[0].state.sample} ; mode {runs[0].state.mode}. "
        "Aucun rendement, IC ou ordre calculé.</p>",
        "<p>Les délais conventionnels ne certifient pas les publications passées. "
        "GPR/EPU restent CONTEMPORARY_INPUT_RETRO_METHOD ; "
        "le dollar est rétrospectif dans R descriptif. "
        "Les données raw exportées sont une archive, pas un signal historique.</p>",
    ]
    include_js = True

    def figure(fig, identifier):
        nonlocal include_js
        html = fig.to_html(full_html=False, include_plotlyjs=include_js, div_id=identifier)
        include_js = False
        sections.append(html)

    for run in runs:
        state = run.state
        prefix = run.ablation
        sections.append(f"<section><h2>{escape(prefix)} — {state.sample} {state.mode}</h2>")
        rows = []
        for name in state.values:
            values = state.values[name]
            valid = values.dropna()
            raw = reference.observations[name]
            raw = raw.loc[raw.date <= state.query_date]
            rows.append(
                {
                    "variable": name,
                    "premier_état": valid.index.min(),
                    "dernier_état": valid.index.max(),
                    "états_manquants": int(values.isna().sum()),
                    "observations_brutes_manquantes": int(raw.value.isna().sum()),
                    "statut": state.statuses[name],
                }
            )
        sections += [
            "<h3>Couverture et valeurs manquantes</h3>",
            "<div class='scroll'>"
            + pd.DataFrame(rows).to_html(index=False, escape=True)
            + "</div>",
        ]
        sections.append(
            f"<p>{len(state.complete)} états complets ; "
            f"minimum pour les distances : {cfg.MIN_HISTORY_SESSIONS}. "
            f"Analogues retenus : {len(run.review_analogues)} / {cfg.ANALOGUE_COUNT}.</p>"
        )
        if not state.values.empty:
            names = list(state.values)
            titles = [
                title for name in names for title in (name, f"{name} — différence quotidienne")
            ]
            plot = make_subplots(rows=len(names), cols=2, subplot_titles=titles)
            for number, name in enumerate(names, 1):
                plot.add_trace(
                    go.Scattergl(
                        x=state.values.index,
                        y=state.values[name],
                        name=name,
                        mode="lines",
                        connectgaps=False,
                        showlegend=False,
                    ),
                    row=number,
                    col=1,
                )
                plot.add_trace(
                    go.Scattergl(
                        x=state.values.index,
                        y=state.values[name].diff(),
                        name=f"Δ {name}",
                        mode="lines",
                        connectgaps=False,
                        showlegend=False,
                    ),
                    row=number,
                    col=2,
                )
            plot.update_layout(
                height=cfg.DIAGNOSTIC_ROW_HEIGHT * len(names),
                title="Variables transformées et différences quotidiennes — sans seuil de rupture",
            )
            figure(plot, prefix + "_variables")
            flags = run.labels.astype("Float64").to_numpy(dtype=float, na_value=np.nan).T
            heatmap = go.Figure(
                go.Heatmap(
                    x=run.labels.index,
                    y=list(run.labels),
                    z=flags,
                    zmin=0,
                    zmax=1,
                    colorbar_title="Étiquette",
                )
            )
            heatmap.update_layout(
                title="Étiquettes multiples — seuils en expansion ; blanc = inconnu"
            )
            figure(heatmap, prefix + "_labels")
        sections += [
            "<h3>Analogues et contributions</h3>",
            "<div class='scroll'>"
            + run.review_analogues.to_html(index=False, escape=True)
            + "</div>",
        ]
        if not run.review_analogues.empty:
            episodes = run.review_analogues
            timeline = go.Figure(
                go.Scatter(
                    x=episodes.representative_date,
                    y=episodes.distance,
                    mode="markers+text",
                    text=episodes["rank"].astype(str),
                    customdata=episodes[["episode_start", "episode_end"]].astype(str).to_numpy(),
                    hovertemplate="%{x}<br>distance=%{y}<br>épisode=%{customdata[0]}"
                    " / %{customdata[1]}<extra></extra>",
                )
            )
            timeline.update_layout(
                title="Carte temporelle des représentants",
                xaxis_title="Date représentative",
                yaxis_title="Distance euclidienne pondérée",
            )
            figure(timeline, prefix + "_map")
            columns = [column for column in episodes if column.startswith("contrib_")]
            contributions = go.Figure(
                go.Heatmap(
                    x=[name.removeprefix("contrib_") for name in columns],
                    y=episodes.representative_date.dt.strftime("%Y-%m-%d"),
                    z=episodes[columns].to_numpy(),
                    zmin=0,
                    zmax=1,
                    colorbar_title="Contribution",
                )
            )
            contributions.update_layout(title="Contributions à la distance au carré")
            figure(contributions, prefix + "_contributions")
        else:
            sections.append(
                "<p>Aucun analogue : historique insuffisant ou état de requête incomplet. "
                "Les seuils ne sont pas relâchés.</p>"
            )
        sensitivities = [
            {
                "séparation_mois": months,
                "q": quantile,
                "nombre": len(result.episodes),
                "représentants": ", ".join(
                    result.episodes.representative_date.dt.strftime("%Y-%m-%d")
                )
                if len(result.episodes)
                else "",
            }
            for (months, quantile), result in run.sensitivities.items()
        ]
        sections += [
            "<h3>Sensibilité — neuf combinaisons prévues</h3>",
            pd.DataFrame(sensitivities).to_html(index=False, escape=True),
            "<h3>Variante robuste médiane / IQR</h3>",
            "<div class='scroll'>"
            + run.robust.episodes.to_html(index=False, escape=True)
            + "</div>",
            "</section>",
        ]
    sections += [
        "<h2>Sources et limites</h2>",
        "<div class='scroll'>"
        + registry[
            [
                "identifier",
                "ablation",
                "provider",
                "source_url",
                "downloaded_at_utc",
                "pit_status",
                "availability_rule",
                "limitations",
            ]
        ].to_html(index=False, escape=True)
        + "</div>",
        "<p>Jointure future : date de prédiction strictement postérieure à la date macro. "
        "Choisir explicitement sample, mode et ablation.</p></body></html>",
    ]
    return "\n".join(sections)
