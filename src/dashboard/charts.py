"""
src/dashboard/charts.py — Plotly interactive visualization library for Streamlit.

All charts use the "plotly_white" template with the enterprise palette to
match the light-mode page background.

IMPORTANT: _BASE_LAYOUT_COMMON does NOT include `margin` so that individual
chart functions can set their own margin without triggering the
"multiple values for keyword argument 'margin'" error in Plotly.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ── ENTERPRISE DESIGN PALETTE ──────────────────────────────────────────────────
COLORS = {
    "primary":    "#2457A6",   # Deep blue — primary accent
    "secondary":  "#0891B2",   # Cyan — secondary
    "accent":     "#D97706",   # Amber — warnings, highlights
    "danger":     "#B91C1C",   # Red — risk, SLA breach
    "success":    "#1D7A4F",   # Green — positive signals
    "purple":     "#7C3AED",   # Violet — AI / special
    "neutral":    "#475569",   # Slate — neutral
    "grid":       "rgba(203, 213, 225, 0.6)",
    "bg_white":   "#FFFFFF",
    "text_dark":  "#172033",
}

ISSUE_PALETTE = [
    "#2457A6",  # PRODUCT
    "#0891B2",  # OTHER
    "#D97706",  # DELIVERY
    "#1D7A4F",  # BILLING
    "#7C3AED",  # RETURNS
    "#B91C1C",  # APP
    "#475569",  # WARRANTY
    "#94A3B8",  # UNKNOWN
]

CHANNEL_COLORS = {
    "chat":      "#2457A6",
    "email":     "#1D7A4F",
    "voice":     "#D97706",
    "social":    "#7C3AED",
    "logistics": "#0891B2",
    "billing":   "#475569",
}

# Base layout WITHOUT margin — each chart sets its own margin explicitly
# to avoid "multiple values for keyword argument 'margin'" errors.
_BASE_LAYOUT_COMMON = dict(
    template="plotly_white",
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    font=dict(family="Inter, -apple-system, sans-serif", color="#172033", size=12),
)


def _apply_base_layout(fig: go.Figure, margin: dict | None = None, **extra) -> go.Figure:
    """Apply the shared base layout then merge per-chart overrides safely."""
    layout = dict(_BASE_LAYOUT_COMMON)
    layout["margin"] = margin or dict(l=20, r=20, t=30, b=40)
    layout.update(extra)
    fig.update_layout(**layout)
    return fig


def chart_weekly_trends(weekly_df: pd.DataFrame) -> go.Figure:
    """
    Weekly ticket creation volume (bars) with dual-axis SLA breach rate (line).
    """
    df = weekly_df.sort_values("week").copy()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=df["week"],
            y=df["tickets_created"],
            name="Tickets Created",
            marker=dict(color=COLORS["primary"], opacity=0.85, line=dict(width=0)),
            hovertemplate="Week: %{x}<br>Tickets: %{y:,}<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=df["week"],
            y=df["sla_breach_rate"] * 100,
            name="SLA Breach Rate (%)",
            mode="lines+markers",
            line=dict(color=COLORS["danger"], width=2.5),
            marker=dict(size=4, color=COLORS["danger"]),
            hovertemplate="Week: %{x}<br>Breach: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )

    _apply_base_layout(
        fig,
        margin=dict(l=20, r=20, t=30, b=60),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(255,255,255,0.8)", bordercolor="#CBD5E1", borderwidth=1,
            font=dict(size=11),
        ),
        hovermode="x unified",
        xaxis=dict(
            showgrid=False,
            title="",
            tickangle=-45,
            nticks=20,
            tickfont=dict(size=10),
            linecolor="#CBD5E1",
        ),
        height=420,
    )
    fig.update_yaxes(
        title_text="Weekly Tickets Created",
        showgrid=True,
        gridcolor=COLORS["grid"],
        linecolor="#CBD5E1",
        title_font=dict(size=11),
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="SLA Breach Rate (%)",
        showgrid=False,
        range=[0, 25],
        linecolor="#CBD5E1",
        title_font=dict(size=11),
        secondary_y=True,
    )
    return fig


def chart_issue_distribution(issue_df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart: ticket volume by operational issue category.
    """
    df = issue_df[issue_df["issue_code"] != "UNKNOWN"].sort_values("ticket_count", ascending=True).copy()
    colors = ISSUE_PALETTE[: len(df)]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["issue_code"],
            x=df["ticket_count"],
            orientation="h",
            name="Ticket Volume",
            marker=dict(color=colors[::-1], line=dict(width=0)),
            text=[f"{v:,}  ({s*100:.1f}%)" for v, s in zip(df["ticket_count"], df["ticket_share"])],
            textposition="outside",
            textfont=dict(size=11, color="#172033"),
            hovertemplate="Issue: %{y}<br>Tickets: %{x:,}<extra></extra>",
            cliponaxis=False,
        )
    )

    _apply_base_layout(
        fig,
        margin=dict(l=20, r=90, t=20, b=30),
        xaxis=dict(
            title="Canonical Tickets",
            showgrid=True,
            gridcolor=COLORS["grid"],
            linecolor="#CBD5E1",
            title_font=dict(size=11),
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title="",
            tickfont=dict(size=12, color="#172033"),
            linecolor="#CBD5E1",
        ),
        height=380,
    )
    return fig


def chart_issue_repeat_rates(issue_df: pd.DataFrame) -> go.Figure:
    """
    Bar chart: repeat contact rate by operational issue.
    """
    df = issue_df[issue_df["issue_code"] != "UNKNOWN"].sort_values("repeat_rate", ascending=False).copy()

    bar_colors = [
        COLORS["danger"] if r > 0.15 else COLORS["accent"] if r > 0.12 else COLORS["primary"]
        for r in df["repeat_rate"]
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["issue_code"],
            y=df["repeat_rate"] * 100,
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=[f"{r*100:.1f}%" for r in df["repeat_rate"]],
            textposition="outside",
            textfont=dict(size=11, color="#172033"),
            hovertemplate="Issue: %{x}<br>Repeat Rate: %{y:.1f}%<extra></extra>",
        )
    )

    _apply_base_layout(
        fig,
        margin=dict(l=20, r=20, t=20, b=30),
        xaxis=dict(title="", showgrid=False, tickfont=dict(size=12, color="#172033"), linecolor="#CBD5E1"),
        yaxis=dict(
            title="Repeat Rate (%)",
            showgrid=True,
            gridcolor=COLORS["grid"],
            linecolor="#CBD5E1",
            title_font=dict(size=11),
            tickfont=dict(size=11),
        ),
        height=370,
    )
    return fig


def chart_channel_issue_breakdown(ch_iss_df: pd.DataFrame) -> go.Figure:
    """
    Stacked bar chart: ticket volume by channel per operational issue.
    """
    fig = px.bar(
        ch_iss_df[ch_iss_df["issue_code"] != "UNKNOWN"],
        x="issue_code",
        y="ticket_count",
        color="channel",
        barmode="stack",
        color_discrete_map=CHANNEL_COLORS,
        template="plotly_white",
    )
    _apply_base_layout(
        fig,
        margin=dict(l=20, r=20, t=40, b=30),
        xaxis=dict(title="", showgrid=False, tickfont=dict(size=12, color="#172033"), linecolor="#CBD5E1"),
        yaxis=dict(
            title="Ticket Volume",
            showgrid=True,
            gridcolor=COLORS["grid"],
            linecolor="#CBD5E1",
            title_font=dict(size=11),
        ),
        legend=dict(
            title="Channel",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#CBD5E1",
            borderwidth=1,
            font=dict(size=11),
        ),
        height=380,
    )
    return fig


def chart_repeat_cost_by_channel(rep_econ_df: pd.DataFrame) -> go.Figure:
    """
    Bar chart: total repeat contact cost by support channel.
    """
    df = rep_econ_df[rep_econ_df["dimension"] == "channel"].sort_values("repeat_cost", ascending=False)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["segment"],
            y=df["repeat_cost"],
            marker=dict(
                color=[CHANNEL_COLORS.get(s, COLORS["primary"]) for s in df["segment"]],
                line=dict(width=0),
            ),
            text=[f"₹{int(v):,}" for v in df["repeat_cost"]],
            textposition="outside",
            textfont=dict(size=11, color="#172033"),
            hovertemplate="Channel: %{x}<br>Repeat Cost: ₹%{y:,.0f}<extra></extra>",
        )
    )
    _apply_base_layout(
        fig,
        margin=dict(l=20, r=20, t=20, b=40),
        xaxis=dict(title="Support Channel", showgrid=False, tickfont=dict(size=12), linecolor="#CBD5E1"),
        yaxis=dict(
            title="Total Repeat Cost (₹)",
            showgrid=True,
            gridcolor=COLORS["grid"],
            linecolor="#CBD5E1",
            title_font=dict(size=11),
        ),
        height=350,
    )
    return fig


def chart_repeat_cost_by_issue(rep_econ_df: pd.DataFrame) -> go.Figure:
    """
    Bar chart: total repeat contact cost by operational issue.
    """
    df = rep_econ_df[rep_econ_df["dimension"] == "issue_code"].sort_values("repeat_cost", ascending=False)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["segment"],
            y=df["repeat_cost"],
            marker=dict(color=ISSUE_PALETTE[: len(df)], line=dict(width=0)),
            text=[f"₹{int(v):,}" for v in df["repeat_cost"]],
            textposition="outside",
            textfont=dict(size=11, color="#172033"),
            hovertemplate="Issue: %{x}<br>Repeat Cost: ₹%{y:,.0f}<extra></extra>",
        )
    )
    _apply_base_layout(
        fig,
        margin=dict(l=20, r=20, t=20, b=40),
        xaxis=dict(title="Operational Issue", showgrid=False, tickfont=dict(size=12), linecolor="#CBD5E1"),
        yaxis=dict(
            title="Total Repeat Cost (₹)",
            showgrid=True,
            gridcolor=COLORS["grid"],
            linecolor="#CBD5E1",
            title_font=dict(size=11),
        ),
        height=350,
    )
    return fig


def chart_csat_by_team(csat_df: pd.DataFrame) -> go.Figure:
    """
    Bar chart: mean CSAT score by support team.
    3.0 reference line marks the midpoint of the 1–5 scale.
    """
    df = csat_df[csat_df["dimension"] == "team"].sort_values("avg_csat", ascending=False)

    bar_colors = [
        COLORS["success"] if v >= 3.5 else COLORS["accent"] if v >= 3.0 else COLORS["danger"]
        for v in df["avg_csat"]
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["segment"],
            y=df["avg_csat"],
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=[f"{v:.2f}" for v in df["avg_csat"]],
            textposition="outside",
            textfont=dict(size=11, color="#172033"),
            hovertemplate="Team: %{x}<br>CSAT: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_hline(
        y=3.0,
        line_dash="dot",
        line_color=COLORS["neutral"],
        line_width=1.5,
        annotation_text="Scale Midpoint (3.0)",
        annotation_font=dict(color=COLORS["neutral"], size=10),
        annotation_position="bottom right",
    )
    _apply_base_layout(
        fig,
        margin=dict(l=20, r=20, t=20, b=40),
        xaxis=dict(title="", showgrid=False, tickangle=-20, tickfont=dict(size=11), linecolor="#CBD5E1"),
        yaxis=dict(
            title="Mean CSAT (1.0–5.0)",
            range=[2.5, 4.2],
            showgrid=True,
            gridcolor=COLORS["grid"],
            linecolor="#CBD5E1",
            title_font=dict(size=11),
        ),
        height=350,
    )
    return fig
