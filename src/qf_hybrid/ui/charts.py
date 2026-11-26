"""Consistent Plotly figures for the local research presentation."""
from __future__ import annotations

import math

import networkx as nx
import plotly.graph_objects as go

from qf_hybrid.ui.sandbox import LABELS, family_label

COLORS = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
          "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9",
          "yellow": "#F0E442", "black": "#262B33"}
MECHANISM_COLORS = dict(zip(LABELS, (COLORS["black"], COLORS["blue"], COLORS["orange"],
                                       COLORS["red"], COLORS["green"], COLORS["purple"],
                                       COLORS["sky"], COLORS["yellow"], "#6B7280")))


def finish(fig: go.Figure, *, height=340, y_title=None, x_title=None) -> go.Figure:
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Atkinson Hyperlegible, Arial, sans-serif", color="#172332", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0),
        margin=dict(t=70, b=50, l=60, r=25),
        xaxis=dict(title=x_title, showgrid=False, zeroline=False),
        yaxis=dict(title=y_title, gridcolor="#DCE4EC", zeroline=False),
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=13),
    )
    return fig


def toy_figure(budget: int, wallets: int, lam: float) -> tuple[go.Figure, dict]:
    root = math.sqrt(budget)
    split_root = math.sqrt(budget * wallets)
    effective = (1-lam)*split_root + lam*root
    raw = max(0, split_root**2-budget)
    soft = max(0, effective**2-budget)
    names = ["Một ví", f"Chia {wallets} ví · QF", f"Nén mềm · λ={lam:.2f}"]
    fig = go.Figure(go.Bar(x=names, y=[0, raw, soft],
                           marker_color=[COLORS["blue"], COLORS["red"], COLORS["green"]],
                    ))
    fig.update_traces(hovertemplate="%{x}<br>Matching thô: %{y:,.2f} USD<extra></extra>",
                      texttemplate="%{y:,.1f}", textposition="outside")
    fig.update_yaxes(range=[0, max(raw, soft, 1) * 1.15])
    return finish(fig, height=310, y_title="Matching thô (USD)"), {
        "one_root": root, "split_root": split_root, "effective_root": effective,
        "raw": raw, "soft": soft,
    }


def cluster_map(rows: list[dict], selected_id: int) -> go.Figure:
    fig = go.Figure()
    for label, color, selector in (
        ("Hợp lệ", COLORS["blue"], lambda r: r["attackers"] == 0),
        ("Pha trộn", COLORS["orange"], lambda r: 0 < r["attackers"] < r["size"]),
        ("Chỉ ví tấn công", COLORS["red"], lambda r: r["attackers"] == r["size"]),
    ):
        subset = [r for r in rows if selector(r)]
        if not subset:
            continue
        fig.add_trace(go.Scatter(x=[r["cohesion"] for r in subset], y=[r["shapley"] for r in subset],
                                 mode="markers+text", name=label,
                                 text=[str(r["id"]) if r["id"] == selected_id else "" for r in subset],
                                 textposition="middle center",
                                 marker=dict(size=[max(12, min(58, 8+5*math.sqrt(r["size"]))) for r in subset],
                                             color=color, opacity=.72, line=dict(width=2, color="#FFFFFF")),
                                 customdata=[[r["id"], r["size"], r["attackers"],
                                              r["lambda_base"], r["lambda_full"]] for r in subset],
                                 hovertemplate="Cụm %{customdata[0]} · %{customdata[1]} ví<br>Ví tấn công: %{customdata[2]}<br>Gắn kết: %{x:.3f}<br>Sₖ: %{y:.3f}<br>λ Base: %{customdata[3]:.3f}<br>λ Full: %{customdata[4]:.3f}<extra></extra>"))
    fig.update_xaxes(range=[-.05, 1.05])
    fig.update_yaxes(range=[-.05, 1.05])
    return finish(fig, height=400, x_title="Độ gắn kết nội cụm", y_title="Tỷ trọng nội cụm Sₖ")


def cluster_network(graph, members: list[str], events: dict) -> go.Figure:
    subgraph = graph.subgraph(members)
    positions = nx.spring_layout(subgraph, seed=42, weight="weight") if members else {}
    edges_x, edges_y = [], []
    for u, v in subgraph.edges:
        edges_x.extend([positions[u][0], positions[v][0], None])
        edges_y.extend([positions[u][1], positions[v][1], None])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edges_x, y=edges_y, mode="lines", showlegend=False,
                             line=dict(color="#CBD5E1", width=1), hoverinfo="skip"))
    for attack, name, color in ((False, "Ví hợp lệ", COLORS["blue"]),
                                (True, "Ví tấn công", COLORS["red"])):
        nodes = [u for u in members if u.startswith("attack_") == attack]
        if not nodes:
            continue
        hover = []
        for u in nodes:
            amounts = [float(value) for (donor, _), value in events.items() if donor == u]
            hover.append(f"{u}<br>{name}<br>Đóng góp: {sum(amounts):,.2f} USD<br>Dự án: {len(amounts)}")
        fig.add_trace(go.Scatter(x=[positions[u][0] for u in nodes], y=[positions[u][1] for u in nodes],
                                 mode="markers", name=name, text=hover, hovertemplate="%{text}<extra></extra>",
                                 marker=dict(color=color, size=11, line=dict(color="#FFFFFF", width=1))))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    return finish(fig, height=400)


def sandbox_bar(rows: list[dict]) -> go.Figure:
    fig = go.Figure()
    for label, key, color in (("Lợi ích tấn công", "gain_pct", COLORS["red"]),
                              ("Tổn hại cộng đồng", "damage_pct", COLORS["blue"])):
        fig.add_trace(go.Bar(name=label, x=[r["label"] for r in rows], y=[r[key] for r in rows],
                             marker_color=color, hovertemplate="%{x}<br>%{y:.3f}% ngân sách quỹ<extra></extra>"))
    fig.update_layout(barmode="group")
    fig.update_xaxes(tickangle=-35)
    return finish(fig, height=420, y_title="% ngân sách quỹ")


def sandbox_frontier(rows: list[dict]) -> go.Figure:
    fig = go.Figure()
    for row in rows:
        fig.add_trace(go.Scatter(x=[row["damage_pct"]], y=[row["gain_pct"]], mode="markers",
                                 name=row["label"],
                                 marker=dict(color=MECHANISM_COLORS.get(row["mechanism"], COLORS["purple"]),
                                             size=15, line=dict(color="white", width=2)),
                                 hovertemplate=f"{row['label']}<br>Tổn hại: %{{x:.3f}}% B<br>Lợi ích: %{{y:.3f}}% B<extra></extra>"))
    fig.add_vline(x=5, line_dash="dash", line_color=COLORS["red"],
                  annotation_text="Ngưỡng 5%", annotation_position="top right")
    return finish(fig, height=420, x_title="Tổn hại cộng đồng (% B)",
                  y_title="Lợi ích tấn công (% B)")


def merkle_path(trace: list[dict], valid: bool) -> go.Figure:
    color = COLORS["green"] if valid else COLORS["red"]
    levels = [row["level"] for row in trace]
    fig = go.Figure()
    for row in trace[1:]:
        i = row["level"]
        fig.add_trace(go.Scatter(x=[i-.8, i], y=[1, 1], mode="lines", showlegend=False,
                                 line=dict(color=color, width=3), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[i-.38, i], y=[0, 1], mode="lines", showlegend=False,
                                 line=dict(color=COLORS["blue"], width=2), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=levels, y=[1]*len(levels), mode="markers+text", name="Nhánh tính lại",
                             marker=dict(size=15, color=color, line=dict(color="white", width=2)),
                             text=["Lá"] + [f"Bước {i}" for i in levels[1:]],
                             textposition="top center", customdata=[row["node"] for row in trace],
                             hovertemplate="%{text}<br>%{customdata}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[i-.38 for i in levels[1:]], y=[0]*len(levels[1:]),
                             mode="markers+text", name="Hash anh em từ proof",
                             marker=dict(size=11, color=COLORS["blue"]),
                             text=[f"Anh em {i}" for i in levels[1:]], textposition="bottom center",
                             customdata=[row["sibling"] for row in trace[1:]],
                             hovertemplate="%{text}<br>%{customdata}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[levels[-1]], y=[1.9], mode="markers+text", name="Root tham chiếu",
                             marker=dict(color=COLORS["black"], size=16), text=["Root tham chiếu"],
                             textposition="top center", customdata=[trace[-1]["expected_node"]],
                             hovertemplate="%{text}<br>%{customdata}<extra></extra>"))
    fig.add_shape(type="line", x0=levels[-1], x1=levels[-1], y0=1, y1=1.9,
                  line=dict(color=color, width=2, dash="dash"))
    fig.update_xaxes(visible=False, range=[-.4, levels[-1]+.4])
    fig.update_yaxes(visible=False, range=[-.35, 2.3])
    return finish(fig, height=310)


def gas_plot(frame, lifecycle=None) -> go.Figure:
    fig = go.Figure()
    if lifecycle is None:
        columns = (("merkle_publish_gas", "Merkle · admin", COLORS["green"]),
                   ("naive_publish_gas", "Mảng trên chain · admin", COLORS["orange"]))
    else:
        suffix = f"_{lifecycle}pct"
        columns = ((f"merkle_lifecycle{suffix}", "Merkle · cả vòng", COLORS["green"]),
                   (f"naive_lifecycle{suffix}", "Mảng trên chain · cả vòng", COLORS["orange"]))
    for column, label, color in columns:
        fig.add_trace(go.Scatter(x=frame["n"], y=frame[column], name=label, mode="lines+markers",
                                 line=dict(color=color, width=3),
                                 hovertemplate="N=%{x:,}<br>%{y:,.0f} gas<extra></extra>"))
    return finish(fig, height=340, x_title="Số khoản chi trả N", y_title="Gas")


def evidence_plot(frame, *, empirical: bool) -> go.Figure:
    fig = go.Figure()
    mechanisms = [key for key in LABELS if key in set(frame["mechanism"])]
    for key in mechanisms:
        subset = frame[frame["mechanism"] == key]
        grouped = subset.groupby("family", sort=False)["delta_A_pos_pct"].median().dropna()
        if grouped.empty:
            continue
        names = [family_label(family) for family in grouped.index]
        fig.add_trace(go.Bar(name=LABELS[key], x=names, y=list(grouped.values*100),
                             marker_color=MECHANISM_COLORS[key],
                             hovertemplate="%{x}<br>Lợi ích tấn công: %{y:.3f}% B<extra></extra>"))
    fig.update_layout(barmode="group")
    fig.update_xaxes(tickangle=-25)
    return finish(fig, height=370, y_title="Trung vị lợi ích tấn công (% B)",
                  x_title="Họ tấn công · dữ liệu " + ("Gitcoin" if empirical else "synthetic"))


def allocation_plot(allocations: dict[str, dict[str, float]]) -> go.Figure:
    fig = go.Figure()
    for mechanism, values in allocations.items():
        label = "Tùy chỉnh của tôi" if mechanism == "custom_soft" else LABELS.get(mechanism, mechanism)
        fig.add_trace(go.Bar(name=label, x=list(values), y=list(values.values()),
                             marker_color=MECHANISM_COLORS.get(mechanism, COLORS["purple"]),
                             hovertemplate="%{x}<br>Phân bổ: %{y:,.2f} USD<extra></extra>"))
    fig.update_layout(barmode="group")
    return finish(fig, height=350, x_title="Dự án", y_title="Phân bổ quỹ (USD)")
