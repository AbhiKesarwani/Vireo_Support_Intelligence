"""
src/dashboard/formatting.py — CSS theme, layout helpers, and numeric formatting for Streamlit.

Design System:
  Background:       #F0F4F9  (blue-gray page)
  Surface:          #FFFFFF  (white cards)
  Primary Text:     #172033  (near-black)
  Secondary Text:   #4A5568  (dark gray)
  Muted Text:       #718096  (medium gray)
  Border:           #CBD5E1  (visible dividers)
  Primary Accent:   #2457A6  (deep blue)
  Positive:         #1D7A4F  (green)
  Warning:          #92600A  (amber)
  Risk:             #B91C1C  (red)
  Neutral:          #475569  (slate)
"""

from __future__ import annotations

from typing import Optional
import streamlit as st


def format_inr(val: Optional[float | int], show_decimals: bool = False) -> str:
    """Format number as Indian Rupee string (e.g. ₹32,48,430)."""
    if val is None:
        return "₹0"
    val = float(val)
    if val < 0:
        return f"-₹{format_inr(abs(val), show_decimals).lstrip('₹')}"

    int_part = int(round(val)) if not show_decimals else int(val)
    s = str(int_part)

    # Indian numbering format: last 3 digits, then groups of 2
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        remaining = s[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted = ",".join(groups) + "," + last3

    if show_decimals:
        cents = f"{val % 1:.2f}"[2:]
        return f"₹{formatted}.{cents}"
    return f"₹{formatted}"


def format_pct(val: Optional[float], decimals: int = 2) -> str:
    """Format decimal as percentage string (e.g. 0.0885 -> '8.85%')."""
    if val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def format_num(val: Optional[int | float]) -> str:
    """Format integer with thousands commas."""
    if val is None:
        return "0"
    return f"{int(round(val)):,}"


def inject_custom_css() -> None:
    """
    Inject professional enterprise analytics CSS.

    Design: Light-mode, high-contrast, clean enterprise CX dashboard.
    Avoids: Dark transparent cards on light background (the previous washed-out look).
    """
    css = """
    <style>
    /* ── TYPOGRAPHY ───────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    /* ── PAGE BACKGROUND ──────────────────────────────────── */
    .stApp {
        background-color: #EEF2F7;
    }

    /* Top-padding for the main content area — works across Streamlit 1.28–1.64 */
    .block-container,
    [data-testid="stMainBlockContainer"],
    [data-testid="stAppViewBlockContainer"] {
        background-color: #EEF2F7;
        padding-top: 2.5rem !important;
        padding-bottom: 2rem !important;
    }

    /* ── PAGE HEADINGS ────────────────────────────────────── */
    .main-title {
        font-size: 1.85rem;
        font-weight: 800;
        color: #172033;
        letter-spacing: -0.025em;
        line-height: 1.2;
        margin-bottom: 0.15rem;
    }
    .sub-title {
        font-size: 0.9rem;
        color: #4A5568;
        margin-bottom: 1.4rem;
        font-weight: 400;
    }
    h2, .stSubheader {
        color: #172033 !important;
        font-weight: 700 !important;
    }

    /* ── KPI CARD COMPONENT ───────────────────────────────── */
    .kpi-card {
        background: #FFFFFF;
        border: 1.5px solid #CBD5E1;
        border-left: 4px solid #2457A6;
        border-radius: 8px;
        padding: 1.1rem 1.25rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06), 0 0 0 0px transparent;
        margin-bottom: 0.75rem;
        transition: box-shadow 0.15s ease, border-left-color 0.15s ease;
    }
    .kpi-card:hover {
        box-shadow: 0 4px 12px rgba(36, 87, 166, 0.12);
        border-left-color: #1A3F7A;
    }
    .kpi-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.07em;
        color: #4A5568;
        margin-bottom: 0.4rem;
    }
    .kpi-val {
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #172033;
        line-height: 1.15;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #4A5568;
        margin-top: 0.3rem;
        line-height: 1.4;
    }

    /* ── BADGE COMPONENT ──────────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 0.18rem 0.55rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .badge-success {
        background: #D1FAE5;
        color: #1D7A4F;
        border: 1px solid #A7F3D0;
    }
    .badge-warning {
        background: #FEF3C7;
        color: #92600A;
        border: 1px solid #FDE68A;
    }
    .badge-danger {
        background: #FEE2E2;
        color: #B91C1C;
        border: 1px solid #FECACA;
    }
    .badge-info {
        background: #DBEAFE;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }
    .badge-neutral {
        background: #F1F5F9;
        color: #475569;
        border: 1px solid #CBD5E1;
    }

    /* ── POLICY / METHODOLOGY CALLOUT BOX ─────────────────── */
    .policy-box {
        background: #EFF6FF;
        border-left: 4px solid #2457A6;
        border-radius: 0 6px 6px 0;
        padding: 0.9rem 1.1rem;
        margin: 1rem 0;
        font-size: 0.875rem;
        color: #172033;
        line-height: 1.6;
    }
    .policy-box strong {
        color: #1A3F7A;
    }

    /* ── SCENARIO WARNING BOX ──────────────────────────────── */
    .scenario-box {
        background: #FFFBEB;
        border-left: 4px solid #D97706;
        border-radius: 0 6px 6px 0;
        padding: 0.9rem 1.1rem;
        margin: 1rem 0;
        font-size: 0.875rem;
        color: #172033;
        line-height: 1.6;
    }
    .scenario-box strong {
        color: #92600A;
    }

    /* ── SIDEBAR REDESIGN ──────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: #172033 !important;
        border-right: 1px solid #0F1729;
    }
    [data-testid="stSidebar"] * {
        color: #CBD5E1 !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        color: #CBD5E1 !important;
        padding: 0.35rem 0.5rem;
        border-radius: 6px;
        display: block;
        transition: background 0.1s ease;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.06) !important;
        color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
        color: #94A3B8 !important;
        font-size: 0.8rem !important;
        line-height: 1.5 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.1) !important;
        margin: 0.75rem 0;
    }
    [data-testid="stSidebar"] .stCaption {
        color: #64748B !important;
        font-size: 0.72rem !important;
    }

    /* ── DATAFRAME TABLE STYLING ───────────────────────────── */
    .stDataFrame {
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 8px;
        overflow: hidden;
    }
    .stDataFrame thead th {
        background-color: #F8FAFC !important;
        color: #172033 !important;
        font-weight: 700 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        border-bottom: 2px solid #CBD5E1 !important;
        padding: 0.65rem 0.8rem !important;
    }
    .stDataFrame tbody td {
        color: #172033 !important;
        font-size: 0.87rem !important;
        padding: 0.55rem 0.8rem !important;
        border-bottom: 1px solid #E2E8F0 !important;
    }
    .stDataFrame tbody tr:hover td {
        background-color: #F0F9FF !important;
    }

    /* ── TABS STYLING ──────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: #F8FAFC;
        border: 1.5px solid #CBD5E1;
        border-radius: 8px 8px 0 0;
        gap: 0;
        padding: 0.2rem;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #4A5568 !important;
        padding: 0.5rem 1.1rem !important;
        border-radius: 6px;
    }
    .stTabs [aria-selected="true"] {
        background: #2457A6 !important;
        color: #FFFFFF !important;
    }

    /* ── DIVIDER ───────────────────────────────────────────── */
    hr {
        border-color: #CBD5E1 !important;
        margin: 1.25rem 0 !important;
    }

    /* ── SLIDER ────────────────────────────────────────────── */
    .stSlider [data-testid="stTickBarMin"],
    .stSlider [data-testid="stTickBarMax"] {
        color: #4A5568 !important;
        font-size: 0.8rem !important;
    }

    /* ── CAPTION ───────────────────────────────────────────── */
    .stCaption {
        color: #4A5568 !important;
        font-size: 0.82rem !important;
    }

    /* ── SECTION CARD WRAPPER ──────────────────────────────── */
    .section-card {
        background: #FFFFFF;
        border: 1.5px solid #CBD5E1;
        border-radius: 8px;
        padding: 1.25rem 1.4rem;
        margin: 0.75rem 0;
    }

    /* ── METRIC LABEL OVERRIDES ────────────────────────────── */
    [data-testid="stMetricLabel"] {
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        color: #4A5568 !important;
    }
    [data-testid="stMetricValue"] {
        font-weight: 800 !important;
        color: #172033 !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    badge_text: str = "",
    badge_type: str = "info",
    accent_color: str = "#2457A6",
) -> None:
    """
    Render a high-contrast enterprise metric card.

    Visual hierarchy: label → value → subtitle → badge
    Left accent border color can be customized per card type.
    """
    badge_html = (
        f'<span class="badge badge-{badge_type}">{badge_text}</span>'
        if badge_text
        else ""
    )
    st.markdown(
        f"""
        <div class="kpi-card" style="border-left-color: {accent_color};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
                <div class="kpi-label">{title}</div>
                {badge_html}
            </div>
            <div class="kpi-val">{value}</div>
            <div class="kpi-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
