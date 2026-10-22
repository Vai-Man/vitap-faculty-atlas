"""Plotly figure builders shared by the Streamlit app and the report.

Colour rules (from the project's data-viz guidelines):
* each school keeps one fixed categorical colour everywhere (colour follows
  the entity, never its rank);
* magnitudes (heatmaps) use a single-hue blue ramp, light -> dark;
* thin marks, recessive grid, one y-axis per chart, text in ink colours.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from . import analytics, config

# Validated 8-slot categorical palette (light mode), fixed order.
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
               "#6250d6", "#e34948"]
SCHOOL_ORDER = ["SCOPE", "SAS", "SENSE", "VISH", "VSB", "VSL", "SMEC", "SBST"]
SCHOOL_COLORS = dict(zip(SCHOOL_ORDER, CATEGORICAL))
BLUE_RAMP = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf",
             "#184f95", "#0d366b"]
RANK_COLORS = {  # ordinal single hue (senior = dark), step >= 250 on light
    "Professor": "#104281", "Professor of Practice": "#1c5cab",
    "Emeritus Professor": "#256abf", "Associate Professor": "#3987e5",
    "Assistant Professor": "#86b6ef", "Adjunct Faculty": "#b7d3f6",
    "Not stated": "#c3c2b7",
}
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"


def style(fig: go.Figure, height: int = 380, title: str | None = None,
          legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height, font=dict(family=FONT, size=13, color=INK2),
        title=dict(text=title, font=dict(size=15, color=INK), x=0, xanchor="left") if title else None,
        margin=dict(l=10, r=20, t=50 if title else 20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#fcfcfb",
        showlegend=legend, legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, color=INK)),
        bargap=0.25,
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=INK2))
    return fig


def school_bar(df: pd.DataFrame) -> go.Figure:
    d = analytics.faculty_by_school(df).sort_values("count")
    fig = go.Figure(go.Bar(
        x=d["count"], y=d["school_code"], orientation="h",
        marker=dict(color=[SCHOOL_COLORS.get(c, MUTED) for c in d["school_code"]],
                    line=dict(color="#fcfcfb", width=2)),
        text=d["count"], textposition="outside", textfont=dict(color=INK2),
        customdata=d[["school", "percent"]],
        hovertemplate="<b>%{customdata[0]}</b><br>%{x} faculty (%{customdata[1]}%)<extra></extra>"))
    fig.update_xaxes(title="Faculty profiles")
    return style(fig, 360, "Faculty profiles by school", legend=False)


def department_sunburst(df: pd.DataFrame) -> go.Figure:
    d = df.assign(dept=df["department"].where(df["department_level"] == "department",
                                              "(no sub-department)"))
    g = d.groupby(["school_code", "dept"]).size().reset_index(name="n")
    total = len(df)
    ids, labels, parents, values, colors, customdata = [], [], [], [], [], []
    for sc, grp in g.groupby("school_code"):
        sc_n = int(grp["n"].sum())
        ids.append(sc); labels.append(sc); parents.append(""); values.append(sc_n)
        colors.append(SCHOOL_COLORS.get(sc, MUTED))
        customdata.append([sc_n, round(100 * sc_n / total, 1)])
        for _, r in grp.iterrows():
            ids.append(f"{sc}/{r['dept']}"); labels.append(r["dept"]); parents.append(sc)
            values.append(int(r["n"])); colors.append(SCHOOL_COLORS.get(sc, MUTED))
            customdata.append([int(r["n"]), round(100 * r["n"] / total, 1)])
    fig = go.Figure(go.Sunburst(ids=ids, labels=labels, parents=parents, values=values,
                                branchvalues="total", marker=dict(colors=colors, line=dict(color="white", width=2)),
                                customdata=customdata,
                                hovertemplate="<b>%{label}</b><br>%{customdata[0]} faculty · %{customdata[1]}% of total<extra></extra>",
                                insidetextorientation="radial"))
    return style(fig, 460, "Schools and departments (inner: school, outer: department)", legend=False)


def rank_stacked(df: pd.DataFrame, percent: bool = True) -> go.Figure:
    pct_ct = analytics.rank_share_by_school(df)
    cnt_ct = analytics.rank_by_school(df)
    ct = pct_ct if percent else cnt_ct
    ct = ct.reindex([s for s in SCHOOL_ORDER if s in ct.index])
    pct_ct = pct_ct.reindex(ct.index)
    cnt_ct = cnt_ct.reindex(ct.index)
    fig = go.Figure()
    for rank in ct.columns:
        if percent:
            cd = list(zip(cnt_ct[rank].values, pct_ct[rank].values))
            tmpl = f"<b>%{{y}}</b><br>{rank}: %{{customdata[1]}}% (%{{customdata[0]}} faculty)<extra></extra>"
        else:
            cd = list(zip(cnt_ct[rank].values, pct_ct[rank].values))
            tmpl = f"<b>%{{y}}</b><br>{rank}: %{{customdata[0]}} faculty (%{{customdata[1]}}%)<extra></extra>"
        fig.add_bar(name=rank, y=ct.index, x=ct[rank], orientation="h",
                    marker=dict(color=RANK_COLORS.get(rank, MUTED), line=dict(color="#fcfcfb", width=2)),
                    customdata=cd, hovertemplate=tmpl)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="% of school's profiles" if percent else "Faculty", range=[0, 100] if percent else None)
    return style(fig, 400, "Academic rank mix by school")


def counts_bar(d: pd.DataFrame, x: str, y: str, title: str, color: str = CATEGORICAL[0],
               height: int = 380, horizontal: bool = True) -> go.Figure:
    d = d.copy()
    # Attach the complementary metric (% if x is count, count if x is %)
    _has_pct = "percent" in d.columns
    _has_cnt = "count" in d.columns or "faculty" in d.columns
    _cnt_col = "count" if "count" in d.columns else ("faculty" if "faculty" in d.columns else None)
    if horizontal:
        d = d.iloc[::-1]
        if x in ("count", "faculty") and _has_pct:
            cd = list(zip(d[x].values, d["percent"].values))
            tmpl = "<b>%{y}</b><br>%{customdata[0]} · %{customdata[1]}%<extra></extra>"
        elif x == "percent" and _cnt_col:
            cd = list(zip(d["percent"].values, d[_cnt_col].values))
            tmpl = "<b>%{y}</b><br>%{customdata[0]}% · %{customdata[1]} profiles<extra></extra>"
        else:
            cd = None
            tmpl = "<b>%{y}</b><br>%{x}<extra></extra>"
        fig = go.Figure(go.Bar(x=d[x], y=d[y], orientation="h",
                               marker=dict(color=color, line=dict(color="#fcfcfb", width=1)),
                               customdata=cd, hovertemplate=tmpl))
    else:
        if x in ("count", "faculty") and _has_pct:
            cd = list(zip(d[x].values, d["percent"].values))
            tmpl = "<b>%{x}</b><br>%{customdata[0]} · %{customdata[1]}%<extra></extra>"
        elif x == "percent" and _cnt_col:
            cd = list(zip(d["percent"].values, d[_cnt_col].values))
            tmpl = "<b>%{x}</b><br>%{customdata[0]}% · %{customdata[1]} profiles<extra></extra>"
        else:
            cd = None
            tmpl = "<b>%{x}</b><br>%{y}<extra></extra>"
        fig = go.Figure(go.Bar(x=d[y], y=d[x], marker=dict(color=color),
                               customdata=cd, hovertemplate=tmpl))
    return style(fig, height, title, legend=False)


def availability_bar(df: pd.DataFrame) -> go.Figure:
    d = analytics.field_availability(df)
    fig = counts_bar(d, "percent", "label", "Profile fields: % of profiles with the field filled",
                     height=520)
    fig.update_traces(
        text=[f"{p:.0f}%" for p in d["percent"].iloc[::-1]], textposition="outside",
        textfont=dict(color=INK2),
        customdata=list(zip(d["percent"].iloc[::-1].values, d["count"].iloc[::-1].values)),
        hovertemplate="<b>%{y}</b><br>%{customdata[0]:.1f}% · %{customdata[1]} profiles<extra></extra>",
    )
    fig.update_xaxes(range=[0, 118], title="% of profiles")
    fig.update_traces(cliponaxis=False)
    return fig


def heatmap(matrix: pd.DataFrame, title: str, zfmt: str = ".0f", suffix: str = "%",
            height: int = 420, zmax: float | None = 100, labels_top: bool = True) -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=matrix.values, x=list(matrix.columns), y=list(matrix.index),
        colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
        zmin=0, zmax=zmax, xgap=2, ygap=2,
        text=[[f"{v:{zfmt}}" for v in row] for row in matrix.values], texttemplate="%{text}",
        textfont=dict(size=11),
        hovertemplate="<b>%{y}</b> · %{x}<br>%{z" + ":" + zfmt + "}" + suffix + "<extra></extra>",
        colorbar=dict(thickness=10, outlinewidth=0)))
    fig.update_xaxes(side="top" if labels_top else "bottom", tickangle=-40)
    fig.update_yaxes(autorange="reversed")
    fig = style(fig, height, title, legend=False)
    if labels_top:
        fig.update_layout(margin=dict(t=150 if title else 110))
    return fig


def availability_heatmap(df: pd.DataFrame) -> go.Figure:
    m = analytics.availability_by_school(df)
    m = m.reindex([s for s in SCHOOL_ORDER if s in m.index])
    return heatmap(m, "Field availability by school (% of profiles)", height=520, labels_top=False)


def completeness_box(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for sc in SCHOOL_ORDER:
        sub = df[df["school_code"] == sc]
        if len(sub):
            fig.add_box(y=sub["completeness"] * 100, name=sc, marker_color=SCHOOL_COLORS[sc],
                        line=dict(width=1.5), boxmean=True,
                        hovertemplate=f"<b>{sc}</b><br>%{{y:.0f}}%<extra></extra>")
    fig.update_yaxes(title="Completeness score (%)", range=[0, 105])
    return style(fig, 380, "Profile completeness by school (12 tracked fields)", legend=False)


def phd_stacked(df: pd.DataFrame) -> go.Figure:
    ct = analytics.phd_categories(df, by_school=True)
    ct = ct.reindex([s for s in SCHOOL_ORDER if s in ct.index]).fillna(0)
    order = ["IIT", "NIT", "IISc", "IISER", "IIIT", "BITS", "VIT", "Foreign",
             "Other / unclassified", "Pursuing", "Not stated"]
    cols = [c for c in order if c in ct.columns]
    share = 100 * ct[cols].div(ct[cols].sum(axis=1), axis=0)
    palette = CATEGORICAL + ["#b7b6ad", "#d6d5cd", "#e9e8e2"]
    colors = dict(zip(order, palette[:8] + ["#a3a29a", "#c9c8c0", "#e1e0d9"]))
    fig = go.Figure()
    for c in cols:
        cd = list(zip(ct[c].values.astype(int), share[c].round(1).values))
        fig.add_bar(name=c, y=share.index, x=share[c].round(1), orientation="h",
                    marker=dict(color=colors[c], line=dict(color="#fcfcfb", width=1.5)),
                    customdata=cd,
                    hovertemplate=f"<b>%{{y}}</b><br>{c}: %{{customdata[1]:.1f}}% (%{{customdata[0]}} faculty)<extra></extra>")
    fig.update_layout(barmode="stack")
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[0, 100], title="% of school's profiles")
    return style(fig, 420, "Where faculty earned their PhD (rule-based categories)")


def research_output_bars(df: pd.DataFrame) -> go.Figure:
    d = analytics.research_output_by_school(df).reindex(
        [s for s in SCHOOL_ORDER if s in df["school_code"].unique()])
    fig = go.Figure()
    cnt_map = {"pct_with_patent": "patents_listed", "pct_with_project": "projects_listed",
               "pct_with_award": "awards_listed"}
    for col, name, c in [("pct_with_patent", "Lists ≥1 patent", CATEGORICAL[0]),
                         ("pct_with_project", "Lists ≥1 funded project", CATEGORICAL[1]),
                         ("pct_with_award", "Lists ≥1 award", CATEGORICAL[2])]:
        # customdata[0]=pct, customdata[1]=total entries listed, customdata[2]=school faculty count
        cd = list(zip(d[col].values, d[cnt_map[col]].values, d["faculty"].values))
        n_faculty = (d[col] / 100 * d["faculty"]).round(0).astype(int)
        cd2 = list(zip(d[col].values, n_faculty.values, d["faculty"].values))
        fig.add_bar(name=name, x=d.index, y=d[col], marker=dict(color=c),
                    customdata=cd2,
                    hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{customdata[0]}}% (%{{customdata[1]}} of %{{customdata[2]}} faculty)<extra></extra>")
    fig.update_layout(barmode="group", bargroupgap=0.08)
    fig.update_yaxes(title="% of school's profiles")
    return style(fig, 380, "Share of profiles listing patents, projects and awards")


def phrase_bar(d: pd.DataFrame, title: str, color: str = CATEGORICAL[0]) -> go.Figure:
    fig = counts_bar(d, "faculty", "phrase", title, color=color, height=max(320, 22 * len(d) + 80))
    fig.update_xaxes(title="Faculty listing the phrase")
    return fig


def network_figure(G: nx.Graph, label_top: int = 18) -> go.Figure:
    """Co-occurrence graph; isolated phrases are dropped and only the
    ``label_top`` strongest hubs are labelled (all names show on hover)."""
    G = G.copy()
    G.remove_nodes_from([n for n in list(G.nodes()) if G.degree(n) == 0])
    if G.number_of_nodes() == 0:
        return style(go.Figure(), 300, "No links at this threshold")
    pos = nx.kamada_kawai_layout(G)
    ex, ey = [], []
    for a, b in G.edges():
        ex += [pos[a][0], pos[b][0], None]
        ey += [pos[a][1], pos[b][1], None]
    edges = go.Scatter(x=ex, y=ey, mode="lines", line=dict(color="#c3c2b7", width=1),
                       hoverinfo="skip")
    nodes = list(G.nodes())
    size = [10 + 1.6 * G.nodes[n]["faculty"] ** 0.8 for n in nodes]
    deg = [G.degree(n) for n in nodes]
    hubs = set(sorted(nodes, key=lambda n: G.degree(n, weight="weight"), reverse=True)[:label_top])
    pts = go.Scatter(
        x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes], mode="markers+text",
        text=[n if n in hubs else "" for n in nodes], hovertext=nodes,
        textposition="top center", textfont=dict(size=11, color=INK),
        marker=dict(size=size, color=deg, colorscale=[[0, "#9ec5f4"], [1, "#104281"]],
                    line=dict(color="white", width=2), showscale=True,
                    colorbar=dict(title="links", thickness=10, outlinewidth=0)),
        customdata=[[G.nodes[n]["faculty"], G.degree(n)] for n in nodes],
        hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]} faculty · %{customdata[1]} links<extra></extra>")
    fig = go.Figure([edges, pts])
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    fig.update_xaxes(visible=False, range=[min(xs) - 0.25, max(xs) + 0.25])
    fig.update_yaxes(visible=False, range=[min(ys) - 0.12, max(ys) + 0.15])
    return style(fig, 620, "Research-phrase co-occurrence network (isolated phrases hidden)", legend=False)


def topic_mix_heatmap(mix: pd.DataFrame) -> go.Figure:
    share = (100 * mix.div(mix.sum(axis=1), axis=0)).round(0)
    share = share.reindex([s for s in SCHOOL_ORDER if s in share.index])
    return heatmap(share, "Dominant NMF topic by school (% of school's profiles)", height=520,
                   labels_top=False)


def similarity_heatmap(sim: pd.DataFrame) -> go.Figure:
    sim = sim.reindex(index=[s for s in SCHOOL_ORDER if s in sim.index],
                      columns=[s for s in SCHOOL_ORDER if s in sim.columns])
    return heatmap(sim, "Research-vocabulary similarity between schools (cosine)",
                   zfmt=".2f", suffix="", zmax=1, height=420)


def k_scan_line(scan: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(x=scan["k"], y=scan["reconstruction_error"], mode="lines+markers",
                               line=dict(color=CATEGORICAL[0], width=2), marker=dict(size=8),
                               hovertemplate="k=%{x}<br>error %{y:.3f}<extra></extra>"))
    fig.update_xaxes(title="Number of topics (k)", dtick=2)
    fig.update_yaxes(title="NMF reconstruction error")
    return style(fig, 320, "Choosing k: reconstruction error vs topic count", legend=False)
