 
     # ForecastPro AI Streamlit app with browser-style tab navigation between workflow steps
# Co-authored with CoCo
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st
import importlib
import data_access as _data_access
_data_access = importlib.reload(_data_access)
from data_access import (
    active_session,
    campaign_names,
    discover_sources,
    account_dimensions,
    historical_preview,
    historical_monthly_preview,
    seasonal_indexes,
    REFERENCE_HISTORICAL_TABLE,
)
from forecast_core import (
    ForecastScenarioInput,
    HistoricalPerformance,
    InvestmentTier,
    MonthlyProjection,
    apply_improvement_factor,
    calculate_standard_projections,
    forecast_ranges,
    load_curve,
    monthly_projections,
)
from planning_source import planning_campaigns, planning_input
from workbook_export import build_workbook


SOURCE_PACKAGE_FILES = (
    "streamlit_app.py", "data_access.py", "forecast_core.py",
    "workbook_export.py", "planning_source.py",
    "signal_utilization_curve.json", "FORECASTING_Q2_2026.csv",
    "pyproject.toml", "snowflake.yml", ".streamlit/config.toml",
)


def build_v3_source_zip() -> bytes:
    """Package the deployable V3 source for teammate testing."""
    root = Path(__file__).resolve().parent
    result = BytesIO()
    with ZipFile(result, "w", ZIP_DEFLATED) as archive:
        for relative_name in SOURCE_PACKAGE_FILES:
            source_file = root / relative_name
            if source_file.is_file():
                archive.write(
                    source_file,
                    arcname=f"forecastpro_snowflake_q2fix_v3/{relative_name}",
                )
        archive.writestr(
            "forecastpro_snowflake_q2fix_v3/README.txt",
            "ForecastPro Snowflake Q2 Fix V3\n\n"
            "Upload this folder to a Snowflake Workspace and run streamlit_app.py.\n"
            "Historical data requires the active Snowflake role to access "
            "ZX.ANALYTICS.ZX_ATTRIBUTION_CUMULATIVE_WEEKLY_PERFORMANCE.\n",
        )
    return result.getvalue()


st.set_page_config(page_title="ForecastPro AI", page_icon="📈", layout="wide")
st.markdown(
    """
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

  /* === BASE: White-dominant premium === */
  html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #FAFAFA !important;
    color: #111111 !important;
  }
  .stApp { background: #FAFAFA !important; }
  .block-container { padding-top: 2rem; max-width: 1600px; background: #FAFAFA !important; }

  /* === TYPOGRAPHY — Strong hierarchy === */
  h1 { color: #111111 !important; font-family: 'DM Serif Display', serif !important; font-weight: 400 !important; font-size: 2.2rem !important; letter-spacing: -0.02em !important; line-height: 1.15 !important; }
  h2 { color: #111111 !important; font-family: 'Space Grotesk', sans-serif !important; font-weight: 600 !important; font-size: 1.5rem !important; letter-spacing: -0.02em !important; }
  h3 { color: #222222 !important; font-family: 'Space Grotesk', sans-serif !important; font-weight: 600 !important; font-size: 1.15rem !important; letter-spacing: -0.01em !important; }
  p, span, label, .stMarkdown, [data-testid="stMarkdownContainer"] { color: #333333 !important; }

  /* === METRICS === */
  [data-testid="stMetric"] { background: transparent !important; border: none !important; padding: 0 !important; }
  [data-testid="stMetricLabel"] {
    color: #666666 !important; font-size: 0.7rem !important; font-weight: 500 !important;
    text-transform: uppercase !important; letter-spacing: 0.06em !important;
  }
  [data-testid="stMetricValue"] { color: #111111 !important; font-size: 1.4rem !important; font-weight: 700 !important; }

  /* === WORKFLOW STEPPER === */
  .workflow {
    background: #FFFFFF;
    border: 1px solid #ECECEC;
    color: #666666;
    padding: .85rem 1.6rem;
    border-radius: 14px;
    margin: .5rem 0 1.5rem;
    letter-spacing: .02em;
    font-weight: 500;
    font-size: 0.9rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .muted { color: #666666; font-size: 0.85rem; }

  /* === METRICS === */
  [data-testid="stMetric"] { background: transparent !important; border: none !important; padding: 0 !important; }
  [data-testid="stMetricLabel"] {
    color: #666666 !important; font-size: 0.75rem !important; font-weight: 500 !important;
    text-transform: uppercase !important; letter-spacing: 0.06em !important;
  }
  [data-testid="stMetricValue"] { color: #111111 !important; font-size: 1.5rem !important; font-weight: 700 !important; }

  /* === KPI CARDS — Floating white cards === */
  .kpi-card {
    background: #FFFFFF;
    border: 1px solid #ECECEC;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 0.85rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
  }
  .kpi-card:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.07);
    transform: translateY(-1px);
  }
  .kpi-label {
    color: #666666;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.4rem;
  }
  .kpi-value {
    color: #111111;
    font-size: 1.5rem;
    font-weight: 700;
  }
  .kpi-value-accent {
    background: linear-gradient(135deg, #0ea65f, #06b6d4, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.5rem;
    font-weight: 700;
  }
  .kpi-hint {
    color: #999999;
    font-size: 0.72rem;
    margin-top: 0.3rem;
    font-style: italic;
  }

  /* === TIER CARDS — Premium floating cards === */
  .tier-card {
    background: #FFFFFF;
    border: 1px solid #ECECEC;
    border-radius: 18px;
    padding: 1.4rem;
    text-align: center;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    position: relative;
    overflow: hidden;
  }
  .tier-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; width: 100%; height: 3px;
    background: linear-gradient(90deg, #0ea65f, #06b6d4, #3b82f6);
    opacity: 0;
    transition: opacity 0.25s ease;
  }
  .tier-card:hover {
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    transform: translateY(-3px);
    border-color: transparent;
  }
  .tier-card:hover::before { opacity: 1; }
  .tier-name {
    color: #666666;
    font-size: 0.76rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
  }
  .tier-amount {
    background: linear-gradient(135deg, #0ea65f, #06b6d4, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.35rem;
    font-weight: 700;
  }

  /* === BUTTONS — Force white for ALL buttons, no dark backgrounds === */
  .stButton > button,
  .stButton > button[kind="secondary"],
  .stButton > button[kind="tertiary"],
  .stButton > button[data-testid],
  [data-testid="baseButton-secondary"],
  [data-testid="baseButton-tertiary"],
  button[kind="secondary"],
  button[kind="tertiary"] {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E0E0E0 !important;
    color: #333333 !important;
    border-radius: 12px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
  }
  .stButton > button:hover,
  .stButton > button[kind="secondary"]:hover,
  .stButton > button[kind="tertiary"]:hover,
  [data-testid="baseButton-secondary"]:hover,
  [data-testid="baseButton-tertiary"]:hover,
  button[kind="secondary"]:hover,
  button[kind="tertiary"]:hover {
    background: #F8F8F8 !important;
    background-color: #F8F8F8 !important;
    border-color: #CCCCCC !important;
    color: #333333 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
    transform: translateY(-1px);
  }
  .stButton > button:active,
  .stButton > button:focus,
  [data-testid="baseButton-secondary"]:active,
  [data-testid="baseButton-secondary"]:focus {
    background: #F0F0F0 !important;
    background-color: #F0F0F0 !important;
    color: #333333 !important;
    border: 1px solid #E0E0E0 !important;
  }
  .stButton > button[kind="primary"],
  [data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #0ea65f, #06b6d4, #3b82f6) !important;
    border: none !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 14px rgba(14,166,95,0.25) !important;
  }
  .stButton > button[kind="primary"]:hover,
  [data-testid="baseButton-primary"]:hover {
    box-shadow: 0 6px 20px rgba(14,166,95,0.35) !important;
    transform: translateY(-1px);
  }

  /* === FORM INPUTS — Clean light fields === */
  [data-testid="stForm"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    border-radius: 18px !important;
    padding: 1.75rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
  }
  input, [data-testid="stTextInput"] input,
  [data-testid="stNumberInput"] input {
    background: #F5F5F5 !important;
    border: 1px solid #E8E8E8 !important;
    border-radius: 10px !important;
    color: #111111 !important;
    caret-color: #0ea65f !important;
    font-weight: 500 !important;
    padding: 0.65rem 1rem !important;
    font-size: 0.95rem !important;
  }
  input:focus, [data-testid="stTextInput"] input:focus,
  [data-testid="stNumberInput"] input:focus {
    border-color: #0ea65f !important;
    box-shadow: 0 0 0 3px rgba(14,166,95,0.1) !important;
    background: #FFFFFF !important;
  }
  [data-testid="stSelectbox"] > div > div {
    background: #F5F5F5 !important;
    border: 1px solid #E8E8E8 !important;
    border-radius: 10px !important;
    color: #111111 !important;
  }
  [data-testid="stSelectbox"] span { color: #111111 !important; }
  [data-testid="stWidgetLabel"], [data-testid="stNumberInput"] label {
    color: #666666 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
  }

  /* === NUMBER INPUT STEPPER BUTTONS — White/grey instead of black === */
  [data-testid="stNumberInput"] button {
    background: #F5F5F5 !important;
    border: 1px solid #E0E0E0 !important;
    color: #666666 !important;
    border-radius: 8px !important;
  }
  [data-testid="stNumberInput"] button:hover {
    background: #ECECEC !important;
    border-color: #CCCCCC !important;
    color: #333333 !important;
  }
  [data-testid="stNumberInput"] button svg {
    fill: #666666 !important;
    stroke: #666666 !important;
  }
  [data-testid="stNumberInput"] button:hover svg {
    fill: #333333 !important;
    stroke: #333333 !important;
  }

  /* === FORM SUBMIT BUTTON — White/grey style === */
  [data-testid="stForm"] button[kind="secondaryFormSubmit"],
  [data-testid="stForm"] [data-testid="stFormSubmitButton"] > button {
    background: #FFFFFF !important;
    border: 1px solid #E0E0E0 !important;
    color: #555555 !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
  }
  [data-testid="stForm"] button[kind="secondaryFormSubmit"]:hover,
  [data-testid="stForm"] [data-testid="stFormSubmitButton"] > button:hover {
    background: #F8F8F8 !important;
    border-color: #CCCCCC !important;
    color: #333333 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
  }

  /* === TABS — Pill style === */
  [data-testid="stTabs"] > div[role="tablist"] {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 5px;
    border: 1px solid #ECECEC;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03);
  }
  [data-testid="stTabs"] > div[role="tablist"] > button {
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.2rem !important;
    color: #666666 !important;
    border-radius: 10px !important;
    transition: all 0.2s ease !important;
  }
  [data-testid="stTabs"] > div[role="tablist"] > button[aria-selected="true"] {
    background: linear-gradient(135deg, #0ea65f, #06b6d4, #3b82f6) !important;
    color: #FFFFFF !important;
    border-bottom-color: transparent !important;
    box-shadow: 0 2px 8px rgba(14,166,95,0.2) !important;
  }
  [data-testid="stTabs"] > div[role="tablist"] > button:hover {
    color: #111111 !important;
    background: #F5F5F5 !important;
  }

  /* === DATAFRAMES — Modern clean tables === */
  [data-testid="stDataFrame"] {
    border-radius: 14px !important;
    overflow: hidden;
    border: 1px solid #ECECEC !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important;
  }
  [data-testid="stDataFrame"] th {
    background: #F8F8F8 !important;
    color: #333333 !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    border-bottom: 1px solid #ECECEC !important;
  }
  [data-testid="stDataFrame"] td {
    background: #FFFFFF !important;
    color: #333333 !important;
    border-color: #F5F5F5 !important;
  }

  /* === DIVIDERS === */
  hr { border-color: #ECECEC !important; margin: 2rem 0 !important; }

  /* === CAPTIONS === */
  .stCaption { color: #999999 !important; font-size: 0.78rem !important; letter-spacing: 0.04em; }

  /* === ALERTS — Soft rounded === */
  [data-testid="stAlert"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    color: #333333 !important;
  }

  /* === SIDEBAR === */
  [data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #ECECEC !important;
  }

  /* === NAV BUTTONS === */
  .nav-buttons {
    display: flex;
    justify-content: space-between;
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid #ECECEC;
  }

  /* === CHECKBOX & RADIO === */
  [data-testid="stCheckbox"] label span { color: #333333 !important; }
  [data-testid="stRadio"] label span { color: #333333 !important; }

  /* === EXPANDER — White card style === */
  [data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #ECECEC !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03) !important;
  }
  [data-testid="stExpander"] summary { color: #333333 !important; font-weight: 600 !important; }

  /* === SUGGESTED BUTTON === */
  .suggested-btn {
    background: rgba(14,166,95,0.06);
    border: 1px solid rgba(14,166,95,0.2);
    color: #0ea65f;
    padding: 0.45rem 1.1rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .suggested-btn:hover {
    background: rgba(14,166,95,0.1);
    border-color: #0ea65f;
    box-shadow: 0 2px 8px rgba(14,166,95,0.12);
  }

  /* === DOWNLOAD BUTTON === */
  [data-testid="stDownloadButton"] > button {
    background: #FFFFFF !important;
    border: 1px solid #3b82f6 !important;
    color: #3b82f6 !important;
    border-radius: 12px !important;
  }
  [data-testid="stDownloadButton"] > button:hover {
    background: rgba(59,130,246,0.04) !important;
    box-shadow: 0 4px 12px rgba(59,130,246,0.12) !important;
  }

  /* === SCROLLBAR === */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #FAFAFA; }
  ::-webkit-scrollbar-thumb { background: #DDD; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #BBB; }

  /* === ANIMATION — Subtle fade in === */
  @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  .kpi-card, .tier-card, [data-testid="stForm"], [data-testid="stDataFrame"] {
    animation: fadeIn 0.4s ease forwards;
  }

  /* === AI INSIGHT CARD === */
  .ai-insight {
    background: linear-gradient(135deg, rgba(14,166,95,0.04), rgba(59,130,246,0.04));
    border: 1px solid rgba(14,166,95,0.15);
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
    margin: 1rem 0;
  }
  .ai-insight-title {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    background: linear-gradient(135deg, #0ea65f, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
  }
  .ai-insight-body {
    color: #333333;
    font-size: 0.88rem;
    line-height: 1.6;
  }

  /* === EXTRA SPACING === */
  [data-testid="stVerticalBlock"] > div { margin-bottom: 0.3rem; }
  [data-testid="stHorizontalBlock"] { gap: 1rem; }

  /* === NUCLEAR: Kill ALL dark backgrounds everywhere === */
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  header, footer,
  section[data-testid="stSidebar"],
  .main, .block-container,
  [data-testid="stBottomBlockContainer"],
  [data-testid="stAppViewBlockContainer"],
  div[data-baseweb],
  [data-testid="stMarkdownContainer"],
  [data-testid="stVerticalBlock"],
  [data-testid="stHorizontalBlock"],
  [data-testid="column"] {
    background: transparent !important;
    background-color: transparent !important;
  }
  [data-testid="stAppViewContainer"] > section > div {
    background-color: #FAFAFA !important;
  }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_state() -> None:
    defaults = {
        "sources": [],
        "campaigns": [],
        "preview": [],
        "confirmed": False,
        "forecast": None,
        "planning_campaigns": [],
        "message": "Discover an approved historical source to begin.",
        "source_account": "FRONTIER",
        "current_budget": 1_279_611.0,
        "cpm": 8.5,
        "planned_reach": 7_923_287.93,
        "signal_utilization": 1.0,
        "max_reach": 10_000_000.0,
        "frequency_at_max": 18.0,
        "selected_source": None,
        "selected_campaign": None,
        "monthly_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def get_session():
    """Get the Snowflake session. Always fresh from the platform — no caching."""
    return active_session()


def reset_for_new_account() -> None:
    """Clear all app state so user can start fresh with a new account."""
    keys_to_clear = [
        "sources", "campaigns", "preview", "confirmed", "forecast",
        "planning_campaigns", "message", "source_account",
        "current_budget", "cpm", "planned_reach", "signal_utilization",
        "max_reach", "frequency_at_max", "_widget_frequency_at_max", "selected_source",
        "selected_campaign", "selected_history", "tier_overrides",
        "applied_planning_key", "active_tab", "num_scenarios",
        "attribution_window",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)


def reset_after_source() -> None:
    st.session_state.pop("_widget_selected_source_v2", None)
    st.session_state.pop("_widget_selected_campaign", None)
    st.session_state.campaigns = []
    st.session_state.preview = []
    st.session_state.monthly_history = []
    st.session_state.confirmed = False
    st.session_state.forecast = None
    for key in (
        "_widget_frequency_at_max",
        "tier_adjustments",
        "manual_tier_values",
        "manual_tier_mode",
        "tier_calculation_signature",
        "tier_scope_signature",
    ):
        st.session_state.pop(key, None)


def money(value) -> str:
    return f"${float(value):,.0f}"


def number(value) -> str:
    return f"{float(value):,.0f}"


def quarter_value(label: str) -> int:
    match = re.fullmatch(r"Q([1-4])\s+(\d{4})", label.strip(), re.I)
    return int(match.group(2)) * 4 + int(match.group(1)) if match else 0


def next_quarter(label: str) -> str:
    match = re.fullmatch(r"Q([1-4])\s+(\d{4})", label.strip(), re.I)
    if not match:
        return "Upcoming quarter"
    quarter, year = int(match.group(1)), int(match.group(2))
    return f"Q1 {year + 1}" if quarter == 4 else f"Q{quarter + 1} {year}"


def visible_tier(label: str, show_expansion: bool) -> bool:
    return show_expansion or not (
        label.startswith("Incremental Reach")
        or label.startswith("Maximum Scale")
        or label.startswith("Extended Scale")
    )


def tab_nav_buttons(tab_names: list[str], current_index: int) -> None:
    """Render Previous / Next navigation buttons at the bottom of a tab."""
    st.markdown("---")
    cols = st.columns([1, 1])
    if current_index > 0:
        with cols[0]:
            if st.button(f"⬅ Previous: {tab_names[current_index - 1]}", key=f"prev_{current_index}"):
                st.session_state.active_tab = current_index - 1
                st.rerun()
    if current_index < len(tab_names) - 1:
        with cols[1]:
            if st.button(f"Next: {tab_names[current_index + 1]} ➡", key=f"next_{current_index}"):
                st.session_state.active_tab = current_index + 1
                st.rerun()


initialize_state()

# --- Get session (simple — no caching, no health checks) ---
session = get_session()

# --- Common header ---
st.markdown(
    '<p style="color:#999;font-size:0.7rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:-0.5rem;">FORECASTPRO AI</p>',
    unsafe_allow_html=True,
)
title_col, reset_col = st.columns([5, 1])
with title_col:
    st.markdown(
        '<h1 style="font-family:\'DM Serif Display\',serif !important;font-weight:2000 !important;font-size: 15rem !important;margin-bottom:0.1rem;">Forecast Engine</h1>'
        '<p style="color:#888;font-size:0.82rem;font-weight:500;margin-top:0;letter-spacing:0.02em;">Forecasting Pod Product</p>',
        unsafe_allow_html=True,
    )
with reset_col:
    if st.button("Start New Account", key="_reset_btn", help="Clear all state and start fresh for next account"):
        reset_for_new_account()
        st.rerun()
    st.download_button(
        "Download V3 source ZIP",
        data=build_v3_source_zip(),
        file_name="forecastpro_snowflake_q2fix_v3.zip",
        mime="application/zip",
        key="download_v3_source_zip",
    )

# st.markdown(
#     '<div class="workflow">'
#     '<span style="color:#16a34a;font-weight:700;">✓ Source</span>'
#     '&nbsp;&nbsp;→&nbsp;&nbsp;'
#     '<span style="color:#16a34a;font-weight:700;">✓ Reconcile</span>'
#     '&nbsp;&nbsp;→&nbsp;&nbsp;'
#     '<span style="color:#16a34a;font-weight:700;">✓ Review</span>'
#     '&nbsp;&nbsp;→&nbsp;&nbsp;'
#     '<span style="background:linear-gradient(135deg,#0ea65f,#06b6d4,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:700;">● Forecast</span>'
#     '&nbsp;&nbsp;→&nbsp;&nbsp;'
#     '<span style="color:#bbb;font-weight:500;">○ Annual</span>'
#     '</div>',
#     unsafe_allow_html=True,
# )
st.info(st.session_state.message)

# =============================================================================
# BUILD TAB LIST — tabs appear progressively as user advances
# =============================================================================
tab_names = ["1 Source & Snapshot"]
if st.session_state.preview:
    tab_names.append("2 Reconcile")
if st.session_state.confirmed:
    tab_names.append("3 Review & Inputs")
if st.session_state.forecast:
    tab_names.append("4 Forecast Results")
    tab_names.append("5 Charts")
    tab_names.append("6 Annual & Quarterly Forecast")

# Initialize active_tab if not set or out of bounds
if "active_tab" not in st.session_state or st.session_state.active_tab >= len(tab_names):
    st.session_state.active_tab = 0

# Render tab bar as buttons
tab_cols = st.columns(len(tab_names))
for i, name in enumerate(tab_names):
    with tab_cols[i]:
        if st.button(name, key=f"tab_btn_{i}", use_container_width=True,
                     type="primary" if i == st.session_state.active_tab else "secondary"):
            st.session_state.active_tab = i
            st.rerun()

st.divider()
active_tab = st.session_state.active_tab


# =============================================================================
# TAB 1: SOURCE & SNAPSHOT (Steps 1 and 2)
# =============================================================================
if active_tab == 0:
    st.header("1. Select historical inputs")
    st.caption(
        "Historical data is read from the cumulative weekly performance table. "        "The table itself is fixed; use the filters below to select the account slice."
    )
    account_identifier = st.text_input(
        "Account name or Account ID",
        value=st.session_state.get("source_account", "FRONTIER"),
    )
    account_rows = session.sql(f"""
        SELECT DISTINCT ACCT_NAME
        FROM {REFERENCE_HISTORICAL_TABLE}
        WHERE ACCT_NAME IS NOT NULL
        ORDER BY ACCT_NAME
    """).collect()
    all_account_options = sorted({
        str(row["ACCT_NAME"]).strip()
        for row in account_rows
        if row["ACCT_NAME"] is not None
    })
    all_account_choice = st.selectbox(
        "All accounts",
        ["(select an account)"] + all_account_options,
        index=(
            0
            if account_identifier.strip() not in all_account_options
            else all_account_options.index(account_identifier.strip()) + 1
        ),
        key="_widget_all_account",
    )
    if all_account_choice != "(select an account)":
        account_identifier = all_account_choice
    window = st.selectbox(
        "Attribution window", options=[7, 14, 21, 30], index=3,
        key="_widget_attribution_window",
    )
    dimensions = {"sub_accounts": [], "events": []}
    if account_identifier.strip():
        try:
            candidate_dimensions = account_dimensions(session, account_identifier.strip(), window)
            if isinstance(candidate_dimensions, list):
                dimensions = {
                    "sub_accounts": sorted({
                        str(row.get("SUB_ACCOUNT")).strip()
                        for row in candidate_dimensions
                        if isinstance(row, dict) and row.get("SUB_ACCOUNT")
                    }),
                    "events": sorted({
                        str(row.get("EVENT")).strip()
                        for row in candidate_dimensions
                        if isinstance(row, dict) and row.get("EVENT")
                    }),
                }
            else:
                dimensions = candidate_dimensions or {"sub_accounts": [], "events": []}
        except Exception as exc:
            st.warning(f"Account filters could not be loaded yet: {exc}")
    sub_options = dimensions.get("sub_accounts", []) or ["(none found)"]

    sub_account_choice = st.selectbox(
        "Sub account",
        sub_options,
        key="_widget_sub_account",
    )

    event_options = []

    if sub_account_choice != "(none found)":
        event_rows = session.sql(
            f"""
            SELECT DISTINCT EVENT
            FROM {REFERENCE_HISTORICAL_TABLE}
            WHERE TO_VARCHAR(ATTRIBUTION_WINDOW) = TO_VARCHAR(?)
              AND (ACCT_NAME ILIKE ? OR TO_VARCHAR(ACCT_ID) ILIKE ?)
              AND UPPER(TRIM(COALESCE(SUB_ACCOUNT, ''))) =
                  UPPER(TRIM(?))
            ORDER BY EVENT
            """,
            params=[
                int(window),
                f"%{account_identifier.strip()}%",
                f"%{account_identifier.strip()}%",
                sub_account_choice,
            ],
        ).collect()

        event_options = sorted(
            {
                str(row["EVENT"]).strip()
                for row in event_rows
                if row["EVENT"] is not None
            }
        )

    event_options = event_options or ["(none found)"]

    event_choice = st.selectbox(
        "Event",
        event_options,
        key="_widget_event",
    )

    table_name = REFERENCE_HISTORICAL_TABLE
    if st.button("Discover campaign series", type="primary"):
        try:
            st.session_state.source_account = account_identifier.strip()
            st.session_state.selected_sub_account = (
                None if sub_account_choice == "(none found)" else sub_account_choice
            )
            st.session_state.selected_event = (
                None if event_choice == "(none found)" else event_choice
            )
            st.session_state.attribution_window = window
            st.session_state.sources = [{"DERIVED_WEEKLY_TABLE": table_name}]
            reset_after_source()
            st.session_state.message = "Historical source filters applied."
            st.rerun()
        except Exception as exc:
            st.error(f"Source filter setup failed: {exc}")

    if st.session_state.sources:
        st.caption(f"Using fixed historical source: {table_name}")
        if st.button("Find campaign series"):
            try:
                try:
                    st.session_state.campaigns = campaign_names(
                        session,
                        table_name,
                        st.session_state.get("attribution_window", 30),
                        account_name=st.session_state.source_account,
                        sub_account=st.session_state.get("selected_sub_account"),
                        event=st.session_state.get("selected_event"),
                    )
                except TypeError as signature_error:
                    if "unexpected keyword argument" not in str(signature_error):
                        raise
                    discovery_filters = ["ATTRIBUTION_WINDOW = ?"]
                    discovery_params = [st.session_state.get("attribution_window", 30)]
                    if st.session_state.source_account:
                        discovery_filters.append("ACCT_NAME ILIKE ?")
                        discovery_params.append(st.session_state.source_account)
                    if st.session_state.get("selected_sub_account"):
                        discovery_filters.append("SUB_ACCOUNT = ?")
                        discovery_params.append(st.session_state.selected_sub_account)
                    if st.session_state.get("selected_event"):
                        discovery_filters.append("EVENT = ?")
                        discovery_params.append(st.session_state.selected_event)
                    discovery_where = " AND ".join(discovery_filters)
                    discovery_rows = session.sql(
                        f"SELECT DISTINCT CAMPAIGN_NAME FROM {table_name} WHERE {discovery_where} ORDER BY 1",
                        params=discovery_params,
                    ).collect()
                    st.session_state.campaigns = [
                        str(row["CAMPAIGN_NAME"])
                        for row in discovery_rows
                        if row["CAMPAIGN_NAME"] is not None
                    ]
                st.session_state.preview = []
                st.session_state.confirmed = False
                st.session_state.forecast = None
                st.session_state.message = (
                    f"Found {len(st.session_state.campaigns)} matching campaign series."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Campaign discovery failed: {exc}")

    if st.session_state.campaigns:
        selected_campaign = st.selectbox(
            "Campaign series", st.session_state.campaigns,
            key="_widget_selected_campaign_v2",
        )
        if st.button("Load final quarterly snapshots", type="primary"):
            try:
                try:
                    rows = historical_preview(
                        session, table_name, selected_campaign,
                        st.session_state.get("attribution_window", 30),
                        account_name=st.session_state.source_account,
                        sub_account=st.session_state.get("selected_sub_account"),
                        event=st.session_state.get("selected_event"),
                    )
                    monthly_rows = historical_monthly_preview(
                        session, table_name, selected_campaign,
                        st.session_state.get("attribution_window", 30),
                        account_name=st.session_state.source_account,
                        sub_account=st.session_state.get("selected_sub_account"),
                        event=st.session_state.get("selected_event"),
                    )
                except TypeError as signature_error:
                    if "unexpected keyword argument" not in str(signature_error):
                        raise
                    rows = historical_preview(
                        session, table_name, selected_campaign,
                        st.session_state.get("attribution_window", 30),
                        account_name=st.session_state.source_account,
                    )
                    monthly_rows = historical_monthly_preview(
                        session, table_name, selected_campaign,
                        st.session_state.get("attribution_window", 30),
                        account_name=st.session_state.source_account,
                    )
                default_keys = {
                    f"{row['campaign_quarter']}-{row['source_week_order']}"
                    for row in [
                        item for item in rows
                        if item["is_complete"] and item["spend_reconciled"]
                    ][:4]
                }
                for row in rows:
                    row["Use"] = f"{row['campaign_quarter']}-{row['source_week_order']}" in default_keys
                st.session_state.preview = rows
                st.session_state.monthly_history = monthly_rows
                st.session_state.confirmed = False
                st.session_state.forecast = None
                st.session_state.selected_source = table_name
                st.session_state.selected_campaign = selected_campaign
                st.session_state.message = "The four most recent complete, reconciled quarters are selected by default."
                st.session_state.active_tab = 1
                st.rerun()
            except Exception as exc:
                st.error(f"Historical preview failed: {exc}")

        tab_nav_buttons(tab_names, 0)


# TAB 2: RECONCILE (Step 3)
# =============================================================================
if st.session_state.preview and active_tab == 1:
    st.header("3. Select, reconcile, and confirm")
    display = pd.DataFrame(
        [
            {
                "Use": row["Use"],
                "Quarter": row["campaign_quarter"],
                "Status": "Complete"
                if row["is_complete"]
                else f"Partial to {row['customer_measure_through']}",
                "Final week": row["source_week_order"],
                "Historical CPM": float(row["historical_cpm"]),
                "Delivered": row["delivered_volume"],
                "Prospects": row["prospects"],
                "Inc. customers": float(row["incremental_customers"]),
                "Revenue": float(row["incremental_revenue"]),
                "CPIx": float(row["cpix"]),
                "iROAS": float(row["iroas"]),
                "Spend check": "Pass"
                if row["spend_reconciled"]
                else f"Difference {row['spend_difference']}",
            }
            for row in st.session_state.preview
        ]
    )
    edited = st.data_editor(
        display,
        hide_index=True,
        use_container_width=True,
        key=f"history_editor_{hash(str([r['campaign_quarter'] for r in st.session_state.preview]))}",
        disabled=[column for column in display.columns if column != "Use"],
        column_config={
            "Use": st.column_config.CheckboxColumn(required=True),
            "Historical CPM": st.column_config.NumberColumn(format="$%.2f"),
            "Delivered": st.column_config.NumberColumn(format="localized"),
            "Prospects": st.column_config.NumberColumn(format="localized"),
            "Inc. customers": st.column_config.NumberColumn(format="localized"),
            "Revenue": st.column_config.NumberColumn(format="$%.0f"),
            "CPIx": st.column_config.NumberColumn(format="$%.2f"),
            "iROAS": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    selected_quarters = set(edited.loc[edited["Use"], "Quarter"].tolist())
    selected_history = [
        row
        for row in st.session_state.preview
        if row["campaign_quarter"] in selected_quarters
    ]
    incomplete = [row for row in selected_history if not row["is_complete"]]
    unreconciled = [row for row in selected_history if not row["spend_reconciled"]]
    partial_approved = st.checkbox(
        "I reviewed and approve the selected partial quarter(s).",
        disabled=not incomplete,
    )
    can_confirm = (
        bool(selected_history)
        and not unreconciled
        and (not incomplete or partial_approved)
    )
    if st.button(
        "Confirm selected historical inputs", disabled=not can_confirm, type="primary"
    ):
        st.session_state.confirmed = True
        st.session_state.selected_history = selected_history
        st.session_state.forecast = None
        st.session_state.message = (
            "Historical inputs confirmed. Configure the planning and forecast inputs."
        )
        st.session_state.active_tab = 2
        st.rerun()

    tab_nav_buttons(tab_names, 1)


# =============================================================================
# TAB 3: REVIEW & INPUTS (Steps 4-5)
# =============================================================================
if st.session_state.confirmed and active_tab == 2:
    selected_history = st.session_state.selected_history
    st.header("4. Historical Quarterly KPIs & Performance")
    metrics = [
        ("Delivered Volume", "delivered_volume"),
        ("Spend", "source_spend"),
        ("Frequency", "frequency"),
        ("Prospects", "prospects"),
        ("Incremental Customers", "incremental_customers"),
        ("Incremental Revenue", "incremental_revenue"),
        ("Avg. Inc. Rev", "average_incremental_revenue"),
        ("CPIx", "cpix"),
        ("iROAS", "iroas"),
    ]
    summary = []
    for label, field in metrics:
        values = [float(row[field]) for row in selected_history]
        summary.append(
            {
                "Metric": label,
                **{
                    row["campaign_quarter"]: value
                    for row, value in zip(selected_history, values)
                },
                "Average": sum(values) / len(values),
            }
        )
    st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)

    st.header("5. Load Q2 planning inputs")
    st.caption(
        "ForecastPro automatically matches the selected account to the approved "
        "Q2 2026 forecast sheet."
    )
    planning_quarter = "Q2 2026"
    try:
        matching_campaigns = planning_campaigns(
            st.session_state.source_account, planning_quarter
        )
        if matching_campaigns:
            planning_key = st.selectbox(
                "Q2 planning campaign",
                matching_campaigns,
                key="selected_planning_campaign",
            )
            if st.session_state.get("applied_planning_key") != planning_key:
                values = planning_input(planning_key, planning_quarter)
                st.session_state.current_budget = float(values["campaign_budget"])
                st.session_state.cpm = float(values["cpm"])
                st.session_state.planned_reach = float(values["planned_reach"])
                st.session_state.max_reach = float(values["maximum_reach"])
                st.session_state.signal_utilization = float(
                    values["signal_utilization"]
                )
                planning_frequency = float(values["frequency_at_max"])
                st.session_state.frequency_at_max = planning_frequency
                st.session_state["_widget_frequency_at_max"] = planning_frequency
                st.session_state.tier_overrides = {}
                st.session_state.tier_adjustments = {}
                st.session_state.applied_planning_key = planning_key
                st.session_state.message = (
                    f"{planning_key} Q2 planning inputs applied automatically."
                )
                st.rerun()
            st.success(
                f"{planning_key} is selected from the approved "
                f"{planning_quarter} forecast sheet."
            )
        else:
            st.warning(
                f'No {planning_quarter} planning campaign matched '
                f'"{st.session_state.source_account}". '
                "You can still enter the planning values manually below."
            )
    except Exception as exc:
        st.error(f"Approved Q2 forecast sheet could not be loaded: {exc}")

    historical_frequency = sum(
        float(row["frequency"]) for row in selected_history
    ) / len(selected_history)

    st.markdown('<div class="section-header">6. Inputs and calculated investment tiers</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-subtitle">Auto-populated values come from the Q2 planning source. '
        'Frequency remains analyst-controlled, with an automatic safeguard when Sustainable Scale '
        'would otherwise fall below Current Budget.</div>',
        unsafe_allow_html=True,
    )

    # --- Read-only display values (row 1) ---
    row1 = st.columns(4)
    current_budget = st.session_state.current_budget
    cpm = st.session_state.cpm
    planned_reach = st.session_state.planned_reach
    max_reach = st.session_state.max_reach
    signal_utilization = st.session_state.signal_utilization

    minimum_viable_frequency = (
        current_budget * 1000 / (max_reach * cpm)
    )
    historical_signal_frequency = (
        historical_frequency / max(signal_utilization, 0.01)
    )
    recommended_frequency = max(
        minimum_viable_frequency, historical_signal_frequency
    )
    frequency_widget_key = "_widget_frequency_at_max"
    if frequency_widget_key not in st.session_state:
        st.session_state[frequency_widget_key] = float(
            st.session_state.frequency_at_max
        )

    frequency_auto_adjusted = False
    if st.session_state.frequency_at_max < minimum_viable_frequency:
        previous_frequency = st.session_state.frequency_at_max
        adjusted_frequency = round(recommended_frequency, 2)
        st.session_state.frequency_at_max = adjusted_frequency
        st.session_state[frequency_widget_key] = adjusted_frequency
        st.session_state.tier_adjustments = {}
        frequency_auto_adjusted = True

    def kpi_card(col, label, value, hint="", accent=False):
        val_class = "kpi-value-accent" if accent else "kpi-value"
        hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
        col.markdown(
            f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="{val_class}">{value}</div>{hint_html}</div>',
            unsafe_allow_html=True,
        )

    kpi_card(row1[0], "Current Budget", money(current_budget))
    kpi_card(row1[1], "Forecast CPM", f"${float(cpm):,.2f}")
    kpi_card(row1[2], "Planned Reach", number(planned_reach))
    kpi_card(row1[3], "Historical Prospect Frequency", f"{historical_frequency:.2f}", "Use to calculate prospects")

    # --- Read-only display values (row 2) ---
    row2 = st.columns(4)
    kpi_card(row2[0], "Current Signal Utilization", f"{int(signal_utilization * 100)}%")
    kpi_card(row2[1], "Max Reach to Maintain Performance", number(max_reach))

    suggested_frequency = recommended_frequency
    freq_for_calc = st.session_state.frequency_at_max
    max_volume_max_signal = max_reach * freq_for_calc
    kpi_card(row2[2], "Max Volume with Max Signal Utilization", number(max_volume_max_signal), accent=True)

    # --- Editable: Frequency at Max Reach Utilization ---
    # The persistent value deliberately has a different key from the widget.
    # Streamlit removes widget keys on another tab; the persistent value must
    # therefore survive Forecast → Review navigation and +/- button reruns.
    freq_col1, freq_col2 = st.columns(2)

    def _frequency_changed():
        st.session_state.frequency_at_max = float(
            st.session_state[frequency_widget_key]
        )
        st.session_state.tier_adjustments = {}
        st.session_state.forecast = None
        st.session_state.message = (
            "Frequency changed. Create a new forecast draft to update results."
        )

    frequency_at_max = freq_col1.number_input(
        "Frequency at Max Reach Utilization",
        min_value=minimum_viable_frequency,
        key=frequency_widget_key,
        on_change=_frequency_changed,
        help=(
            f"Minimum {minimum_viable_frequency:.2f} keeps Sustainable Scale "
            "at or above Current Budget."
        ),
    )
    st.session_state.frequency_at_max = float(frequency_at_max)
    freq_col1.caption(
        f"Recommended: {suggested_frequency:.2f}. Minimum safe value: "
        f"{minimum_viable_frequency:.2f}."
    )

    def _apply_suggested():
        value = round(suggested_frequency, 2)
        st.session_state.frequency_at_max = value
        st.session_state[frequency_widget_key] = value
        st.session_state.tier_adjustments = {}
        st.session_state.forecast = None
        st.session_state.message = (
            "Recommended frequency applied. Create a new forecast draft to update results."
        )

    freq_col1.button(
        f"Use recommended {suggested_frequency:.2f}",
        on_click=_apply_suggested,
    )
    freq_col1.caption("Analyst override is permitted above the minimum safe value.")
    if frequency_auto_adjusted:
        freq_col2.info(
            f"Frequency was automatically raised from {previous_frequency:.2f} "
            f"to {frequency_at_max:.2f} because the Q2 value would place "
            "Sustainable Scale below Current Budget."
        )

    # Calculated values
    max_investment = max_reach * frequency_at_max * cpm / 1000
    maximum_scale = (max_reach * 1.25) * frequency_at_max / 1000 * cpm
    extended_scale = (max_reach * 1.50) * frequency_at_max / 1000 * cpm

    calc_row = st.columns(3)
    kpi_card(calc_row[0], "Max Investment with Max Signal Utilization", money(max_investment), accent=True)
    kpi_card(calc_row[1], "Maximum Scale (1.25x)", money(maximum_scale), accent=True)
    kpi_card(calc_row[2], "Extended Scale (1.5x)", money(extended_scale),
             hint="For accounts at 90-100% utilization where standard tiers are compressed", accent=True)

    # --- One-quarter range adjustment ---
    range_col1, range_col2 = st.columns(2)
    range_percent = range_col1.number_input(
        "One-quarter range adjustment",
        min_value=0,
        max_value=99,
        value=10,
        key="range_percent_input",
    )
    range_col1.caption("10% uncertainty for one historical quarter")

    st.divider()

    # --- Calculated Investment Tiers ---
    st.subheader("Calculated investment tiers")
    high_utilization = float(signal_utilization) >= 0.90
    at_full_utilization = float(signal_utilization) >= 1.0
    labels = [
        "Baseline",
        "Steady Growth",
        "Core Growth",
        "Accelerated Growth",
        "Breakout Growth",
        "Sustainable Scale",
    ]

    if at_full_utilization:
        # Current Budget is already Sustainable at 100% utilization.
        labels = ["Sustainable Scale"]
        calculated_tier_values = [current_budget]
        minimum_tier_gap = 0.01
    elif high_utilization:
        midpoint = (current_budget + max_investment) / 2
        labels = ["Baseline", "Core Growth", "Sustainable Scale"]
        calculated_tier_values = [current_budget, midpoint, max_investment]
        minimum_tier_gap = 0.01
    else:
        interval = (max_investment - current_budget) / 5
        minimum_tier_gap = min(
            0.01, max((max_investment - current_budget) / 5, 0.0)
        )
        calculated_tier_values = [
            current_budget + interval * index for index in range(6)
        ]

    tier_headroom = float(max_investment) - float(current_budget)
    has_tier_headroom = tier_headroom > 0.01

    # Store relative adjustments, never replacement investment values. This means
    # a +/- action changes only the selected tier and cannot make the remaining
    # tiers fall back to Current Budget.
    st.session_state.setdefault("tier_adjustments", {})
    st.session_state.setdefault("manual_tier_mode", False)
    st.session_state.setdefault("manual_tier_values", {})

    tier_scope_signature = (
        st.session_state.get("source_account"),
        st.session_state.get("selected_sub_account"),
        st.session_state.get("selected_event"),
        st.session_state.get("selected_campaign"),
        tuple(labels),
    )
    if st.session_state.get("tier_scope_signature") != tier_scope_signature:
        st.session_state.manual_tier_mode = False
        st.session_state.manual_tier_values = {}
        st.session_state.tier_scope_signature = tier_scope_signature

    tier_calculation_signature = (
        tier_scope_signature,
        tuple(round(float(value), 6) for value in calculated_tier_values),
    )
    if st.session_state.get("tier_calculation_signature") != tier_calculation_signature:
        st.session_state.tier_adjustments = {}
        st.session_state.tier_calculation_signature = tier_calculation_signature
        if st.session_state.get("forecast") is not None:
            st.session_state.forecast = None
            st.session_state.message = (
                "Forecast inputs changed. Create a new forecast draft to update results."
            )

    def _clear_stale_forecast(message: str) -> None:
        st.session_state.forecast = None
        st.session_state.message = message

    def _manual_tier_changed() -> None:
        _clear_stale_forecast(
            "Manual tier values changed. Create a new forecast draft to update results."
        )

    def _calculated_values_with_adjustments() -> list[float]:
        values = [float(calculated_tier_values[0])]
        for index in range(1, len(calculated_tier_values) - 1):
            label = labels[index]
            base_value = float(calculated_tier_values[index])
            requested_value = base_value + float(
                st.session_state.tier_adjustments.get(label, 0.0)
            )
            lower_bound = values[-1] + minimum_tier_gap
            upper_bound = float(calculated_tier_values[-1]) - (
                minimum_tier_gap * (len(calculated_tier_values) - 1 - index)
            )
            values.append(min(max(requested_value, lower_bound), upper_bound))
        if len(calculated_tier_values) > 1:
            values.append(float(calculated_tier_values[-1]))
        return values

    mode_col, step_col = st.columns([3, 1])
    with mode_col:
        if at_full_utilization:
            st.caption(
                "At 100% utilization, Current Budget is the fixed Sustainable Scale. "
                "Only the extension tiers are forecast."
            )
            st.session_state.manual_tier_mode = False
        elif st.session_state.manual_tier_mode:
            st.caption(
                "Manual tier mode is active. Enter the displayed investment values directly."
            )
            if st.button("Use calculated tiers", key="use_calculated_tiers"):
                st.session_state.manual_tier_mode = False
                st.session_state.manual_tier_values = {}
                _clear_stale_forecast(
                    "Manual tiers cleared. Create a new forecast draft to see calculated tiers."
                )
                st.rerun()
        else:
            st.caption(
                "Calculated values are active. Switch modes to enter investment tiers manually."
            )
            if st.button("Edit tiers manually", key="edit_tiers_manually"):
                current_values = _calculated_values_with_adjustments()
                st.session_state.manual_tier_mode = True
                st.session_state.manual_tier_values = {
                    label: float(value)
                    for label, value in zip(labels, current_values)
                }
                for index, value in enumerate(current_values):
                    st.session_state[f"manual_tier_{index}"] = float(value)
                _clear_stale_forecast(
                    "Manual tier mode is active. Create a new forecast draft after editing values."
                )
                st.rerun()

    with step_col:
        adjustment_step = st.number_input(
            "Adjustment step",
            min_value=1000,
            value=50000,
            step=10000,
            key="_adj_step",
            disabled=st.session_state.manual_tier_mode or at_full_utilization,
        )

    show_expansion = False
    if st.session_state.manual_tier_mode and not at_full_utilization:
        st.caption("Manual values replace the calculated investment tiers for this forecast.")
        st.caption("Enter values in strictly increasing order from left to right.")
        manual_cols = st.columns(3)
        tier_values = []
        for index, (label, calculated_value) in enumerate(
            zip(labels, calculated_tier_values)
        ):
            with manual_cols[index % 3]:
                value = st.number_input(
                    f"{label} investment",
                    min_value=0.01,
                    value=float(
                        st.session_state.manual_tier_values.get(
                            label, calculated_value
                        )
                    ),
                    step=float(adjustment_step),
                    format="%.2f",
                    key=f"manual_tier_{index}",
                    on_change=_manual_tier_changed,
                )
                tier_values.append(float(value))
                st.session_state.manual_tier_values[label] = float(value)
    else:
        if not at_full_utilization and not has_tier_headroom:
            st.warning(
                "Calculated tiers are unavailable because Max Investment equals "
                "Current Budget. Increase Frequency at Max Reach Utilization "
                "(the recommended value restores calculated headroom), or switch "
                "to manual tier mode and enter a strictly increasing tier ladder."
            )
        tier_values = _calculated_values_with_adjustments()
        tier_cols = (
            st.columns(3)
            if high_utilization
            else st.columns(3) + st.columns(3)
        )
        for index, (label, value) in enumerate(zip(labels, tier_values)):
            with tier_cols[index]:
                st.markdown(
                    f'<div class="tier-card"><div class="tier-name">{label}</div>'
                    f'<div class="tier-amount">{money(value)}</div></div>',
                    unsafe_allow_html=True,
                )
                if (
                    not high_utilization
                    and has_tier_headroom
                    and 0 < index < len(labels) - 1
                ):
                    def _change_tier(
                        label_name=label,
                        current_value=value,
                        tier_index=index,
                        direction=0,
                    ):
                        step = float(st.session_state.get("_adj_step", 50000))
                        lower_bound = tier_values[tier_index - 1] + minimum_tier_gap
                        upper_bound = tier_values[tier_index + 1] - minimum_tier_gap
                        new_value = min(
                            max(current_value + direction * step, lower_bound),
                            upper_bound,
                        )
                        base_value = float(calculated_tier_values[tier_index])
                        st.session_state.tier_adjustments[label_name] = (
                            new_value - base_value
                        )
                        _clear_stale_forecast(
                            f"{label_name} adjusted. Create a new forecast draft to update results."
                        )

                    decrease_col, increase_col = st.columns(2)
                    decrease_col.button(
                        "➖",
                        key=f"dec_{index}",
                        on_click=_change_tier,
                        kwargs={"direction": -1},
                    )
                    increase_col.button(
                        "➕",
                        key=f"inc_{index}",
                        on_click=_change_tier,
                        kwargs={"direction": 1},
                    )
    st.divider()

    # --- Improvement Scenarios ---
    st.subheader("Improvement scenarios")
    st.markdown(
        '<div class="section-subtitle">Each scenario assumes a performance improvement '
        'factor (e.g., new model, new channel). Add up to 10 independent scenarios.</div>',
        unsafe_allow_html=True,
    )

    if "num_scenarios" not in st.session_state:
        st.session_state.num_scenarios = 2

    def _add_scenario():
        if st.session_state.num_scenarios < 10:
            st.session_state.num_scenarios += 1

    num_scenarios = st.session_state.num_scenarios
    scenario_factors = []
    scenario_names = []

    for row_start in range(0, num_scenarios, 5):
        row_end = min(row_start + 5, num_scenarios)
        cols = st.columns(row_end - row_start)
        for idx, col in enumerate(cols):
            scenario_idx = row_start + idx
            name = col.text_input(
                f"Scenario {scenario_idx + 1} name",
                value=f"Scenario {scenario_idx + 1}",
                key=f"scenario_name_{scenario_idx}",
            )
            factor = col.number_input(
                f"Factor {scenario_idx + 1} (%)",
                min_value=0.0,
                max_value=99.0,
                value=10.0,
                key=f"scenario_factor_{scenario_idx}",
            )
            scenario_names.append(name)
            scenario_factors.append(factor)

    if num_scenarios < 10:
        st.button("+ Add scenario", on_click=_add_scenario)

    st.divider()

    tiers_strictly_increasing = (
        len(tier_values) <= 1
        or all(left < right for left, right in zip(tier_values, tier_values[1:]))
    )
    calculated_tiers_available = (
        at_full_utilization
        or st.session_state.manual_tier_mode
        or has_tier_headroom
    )
    forecast_ready = (
        max_investment >= current_budget
        and tiers_strictly_increasing
        and calculated_tiers_available
    )
    if not forecast_ready:
        if not calculated_tiers_available:
            st.error(
                "Forecast is paused: there is no calculated headroom above Current "
                "Budget. Use the recommended frequency or enter strictly increasing "
                "manual tiers."
            )
        else:
            st.error(
                "Forecast is paused because investment tiers must be in strictly "
                "increasing order. Review the tier values before recalculating."
            )

    with st.form("forecast_inputs"):
        calculate = st.form_submit_button(
            "Create forecast draft",
            type="primary",
            use_container_width=True,
            disabled=not forecast_ready,
        )

    if calculate:
        try:
            version, curve = load_curve()
            scenario = ForecastScenarioInput(
                Decimal(str(current_budget)),
                Decimal(str(cpm)),
                Decimal(str(round(historical_frequency, 8))),
                Decimal(str(signal_utilization)),
                Decimal(str(max_reach)),
                Decimal(str(frequency_at_max)),
                tuple(
                    InvestmentTier(label, Decimal(str(round(val, 2))))
                    for label, val in zip(labels, tier_values)
                ),
                tuple(
                    HistoricalPerformance(
                        row["campaign_quarter"],
                        row["cpix"],
                        row["average_incremental_revenue"],
                    )
                    for row in selected_history
                ),
                curve,
            )
            projections = calculate_standard_projections(scenario)
            method, ranges = forecast_ranges(
                projections, Decimal(str(range_percent / 100))
            )
            st.session_state.forecast = {
                "version": version,
                "method": method,
                "projections": projections,
                "ranges": ranges,
                "improvements": [
                    (
                        scenario_names[i],
                        Decimal(str(scenario_factors[i] / 100)),
                        apply_improvement_factor(
                            projections, Decimal(str(scenario_factors[i] / 100))
                        ),
                    )
                    for i in range(num_scenarios)
                ],
                "show_expansion": show_expansion,
            }
            st.session_state.message = "Forecast draft created. Review the ranges, quality checks, and marginal economics."
            st.session_state.active_tab = 3
            st.rerun()
        except Exception as exc:
            st.error(f"Forecast calculation failed: {exc}")

    tab_nav_buttons(tab_names, 2)


# =============================================================================
# TAB 4: FORECAST RESULTS
# =============================================================================
if st.session_state.forecast and active_tab == 3:
    result = st.session_state.forecast
    visible_ranges = [
        row for row in result["ranges"]
        if visible_tier(row.tier_label, result["show_expansion"])
    ]
    visible_projections = [
        row for row in result["projections"]
        if visible_tier(row.tier_label, result["show_expansion"])
    ]
    latest_quarter = max(
        (row["campaign_quarter"] for row in st.session_state.selected_history),
        key=quarter_value,
    )
    upcoming = next_quarter(latest_quarter)
    curve_inputs = {
        row.tier_label: row
        for row in result["projections"]
        if row.historical_quarter == latest_quarter
    }

    st.header("Forecast Output Ranges")
    st.caption(f"{result['method']} · curve {result['version']}")
    range_frame = pd.DataFrame([
        {"Tier": row.tier_label, "Investment": float(row.investment),
         "Delivered": float(row.delivered_volume), "Prospects": float(row.prospects),
         "Customers Min": float(row.incremental_customers.minimum),
         "Customers Max": float(row.incremental_customers.maximum),
         "Revenue Min": float(row.incremental_revenue.minimum),
         "Revenue Max": float(row.incremental_revenue.maximum),
         "CPIx Min": float(row.cpix.minimum), "CPIx Max": float(row.cpix.maximum),
         "iROAS Min": float(row.iroas.minimum), "iROAS Max": float(row.iroas.maximum),
         "New Signal Utilization": float(
             curve_inputs[row.tier_label].new_signal_utilization * 100
         ),
         "Adjustment Factor": float(
             curve_inputs[row.tier_label].adjustment_factor * 100
         )}
        for row in visible_ranges
    ])
    st.dataframe(range_frame, hide_index=True, use_container_width=True,
        column_config={
            **{
                col: st.column_config.NumberColumn(format="$%.2f")
                for col in ["Investment", "Revenue Min", "Revenue Max", "CPIx Min", "CPIx Max"]
            },
            "New Signal Utilization": st.column_config.NumberColumn(format="%.1f%%"),
            "Adjustment Factor": st.column_config.NumberColumn(format="%.1f%%"),
        })

    # --- Expansion tiers (hidden by default, toggle to show) ---
    expansion_ranges = [
        row for row in result["ranges"]
        if not visible_tier(row.tier_label, False)
    ]
    if expansion_ranges:
        with st.expander("Show Expansion Tiers (Incremental Reach / Maximum Scale)", expanded=False):
            st.caption("Extended reach tiers beyond Sustainable Scale for high-utilization scenarios.")
            expansion_frame = pd.DataFrame([
                {"Tier": row.tier_label, "Investment": float(row.investment),
                 "Delivered": float(row.delivered_volume), "Prospects": float(row.prospects),
                 "Customers Min": float(row.incremental_customers.minimum),
                 "Customers Max": float(row.incremental_customers.maximum),
                 "Revenue Min": float(row.incremental_revenue.minimum),
                 "Revenue Max": float(row.incremental_revenue.maximum),
                 "CPIx Min": float(row.cpix.minimum), "CPIx Max": float(row.cpix.maximum),
                 "iROAS Min": float(row.iroas.minimum), "iROAS Max": float(row.iroas.maximum),
                 "New Signal Utilization": float(
                     curve_inputs[row.tier_label].new_signal_utilization * 100
                 ),
                 "Adjustment Factor": float(
                     curve_inputs[row.tier_label].adjustment_factor * 100
                 )}
                for row in expansion_ranges
            ])
            st.dataframe(expansion_frame, hide_index=True, use_container_width=True,
                column_config={
                    **{
                        col: st.column_config.NumberColumn(format="$%.2f")
                        for col in ["Investment", "Revenue Min", "Revenue Max", "CPIx Min", "CPIx Max"]
                    },
                    "New Signal Utilization": st.column_config.NumberColumn(format="%.1f%%"),
                    "Adjustment Factor": st.column_config.NumberColumn(format="%.1f%%"),
                })

    detail_tabs = st.tabs(["Marginal economics", "Investment trade-offs", "Improvement scenarios", "Historical reconciliation"])
    with detail_tabs[0]:
        marginal = [row for row in visible_projections if row.historical_quarter == latest_quarter]
        st.caption(f"{upcoming}, based on {latest_quarter}.")
        st.dataframe(pd.DataFrame([
            {"Tier": row.tier_label, "Investment": float(row.investment),
             "Marginal CPIx": float(row.marginal_cpix) if row.marginal_cpix and row.tier_label != "Baseline" else None,
             "Marginal iROAS": float(row.marginal_iroas) if row.marginal_iroas and row.tier_label != "Baseline" else None,
             "New Signal Utilization": float(row.new_signal_utilization * 100),
             "Adjustment Factor": float(row.adjustment_factor * 100)}
            for row in marginal
        ]), hide_index=True, use_container_width=True)
    with detail_tabs[1]:
        chart_data = pd.DataFrame([
            {"Tier": row.tier_label, "Investment": float(row.investment),
             "CPIx midpoint": float((row.cpix.minimum + row.cpix.maximum) / 2),
             "iROAS midpoint": float((row.iroas.minimum + row.iroas.maximum) / 2)}
            for row in visible_ranges
        ])
        left, right = st.columns(2)
        left.altair_chart(alt.Chart(chart_data).mark_line(point=True).encode(
            x=alt.X("Tier:N", sort=None), y="CPIx midpoint:Q", tooltip=list(chart_data.columns)
        ).properties(title="CPIx rises with investment"), use_container_width=True)
        right.altair_chart(alt.Chart(chart_data).mark_line(point=True).encode(
            x=alt.X("Tier:N", sort=None), y="iROAS midpoint:Q", tooltip=list(chart_data.columns)
        ).properties(title="iROAS declines with investment"), use_container_width=True)
    with detail_tabs[2]:
        for name, factor, rows in result["improvements"]:
            st.markdown(f'<div class="kpi-card" style="margin-top:1rem;">'
                f'<div class="kpi-label">{name}</div>'
                f'<div class="kpi-value">+{float(factor)*100:.0f}% improvement</div></div>', unsafe_allow_html=True)
            scenario_rows = [
                {"Tier": r.tier_label, "Investment": float(r.investment),
                 "Inc. Customers": float(r.incremental_customers), "Revenue": float(r.incremental_revenue),
                 "CPIx": float(r.cpix), "iROAS": float(r.iroas)}
                for r in rows if r.historical_quarter == latest_quarter
                and visible_tier(r.tier_label, result["show_expansion"])]
            if scenario_rows:
                st.dataframe(pd.DataFrame(scenario_rows), hide_index=True, use_container_width=True)
    with detail_tabs[3]:
        st.dataframe(pd.DataFrame([{**asdict(row)} for row in visible_projections]),
            hide_index=True, use_container_width=True)

    workbook = build_workbook(st.session_state.source_account, st.session_state.selected_campaign,
        datetime.now(timezone.utc).isoformat(), visible_ranges, result["ranges"], st.session_state.selected_history)
    safe_account = re.sub(r"[^a-z0-9]+", "-", st.session_state.source_account.lower()).strip("-") or "forecast"
    st.download_button("Download Excel workbook", workbook, f"{safe_account}-forecast.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

    tab_nav_buttons(tab_names, 3)


# =============================================================================
# TAB 5: CHARTS (all tiers from Baseline to Maximum Scale)
# =============================================================================
if st.session_state.forecast and active_tab == 4:
    result = st.session_state.forecast
    # Use ALL tiers (standard + expansion) for charts
    all_ranges = sorted(result["ranges"], key=lambda r: float(r.investment))
    latest_quarter = max(
        (row["campaign_quarter"] for row in st.session_state.selected_history),
        key=quarter_value,
    )

    st.header("Forecast Charts")
    st.caption("Visual comparison of all tiers from Baseline through Maximum Scale (+25%).")

    # Build chart dataframe with ALL tiers
    chart_df = pd.DataFrame([
        {
            "Tier": row.tier_label,
            "Investment": float(row.investment),
            "CPIx Min": float(row.cpix.minimum),
            "CPIx Max": float(row.cpix.maximum),
            "CPIx Midpoint": float((row.cpix.minimum + row.cpix.maximum) / 2),
            "iROAS Min": float(row.iroas.minimum),
            "iROAS Max": float(row.iroas.maximum),
            "iROAS Midpoint": float((row.iroas.minimum + row.iroas.maximum) / 2),
            "Customers Min": float(row.incremental_customers.minimum),
            "Customers Max": float(row.incremental_customers.maximum),
            "Customers Midpoint": float((row.incremental_customers.minimum + row.incremental_customers.maximum) / 2),
            "Revenue Min": float(row.incremental_revenue.minimum),
            "Revenue Max": float(row.incremental_revenue.maximum),
            "Revenue Midpoint": float((row.incremental_revenue.minimum + row.incremental_revenue.maximum) / 2),
            "Delivered": float(row.delivered_volume),
            "Prospects": float(row.prospects),
        }
        for row in all_ranges
    ])
    tier_order = chart_df["Tier"].tolist()

    # --- Chart 1: CPIx across all tiers ---
    st.subheader("CPIx by Investment Tier")
    cpix_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#00d4aa").encode(
        x=alt.X("Tier:N", sort=tier_order, title="Tier"),
        y=alt.Y("CPIx Min:Q", title="CPIx ($)"),
        y2="CPIx Max:Q",
    )
    cpix_line = alt.Chart(chart_df).mark_line(point=True, color="#00d4aa", strokeWidth=2.5).encode(
        x=alt.X("Tier:N", sort=tier_order),
        y=alt.Y("CPIx Midpoint:Q", title="CPIx ($)"),
        tooltip=["Tier", "CPIx Min", "CPIx Midpoint", "CPIx Max", "Investment"],
    )
    st.altair_chart(
        (cpix_band + cpix_line).properties(title="CPIx increases as investment exceeds Sustainable Scale", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 2: iROAS across all tiers ---
    st.subheader("iROAS by Investment Tier")
    iroas_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#4da6ff").encode(
        x=alt.X("Tier:N", sort=tier_order, title="Tier"),
        y=alt.Y("iROAS Min:Q", title="iROAS"),
        y2="iROAS Max:Q",
    )
    iroas_line = alt.Chart(chart_df).mark_line(point=True, color="#4da6ff", strokeWidth=2.5).encode(
        x=alt.X("Tier:N", sort=tier_order),
        y=alt.Y("iROAS Midpoint:Q", title="iROAS"),
        tooltip=["Tier", "iROAS Min", "iROAS Midpoint", "iROAS Max", "Investment"],
    )
    st.altair_chart(
        (iroas_band + iroas_line).properties(title="iROAS declines with diminishing returns at higher investment", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 3: Incremental Customers across all tiers ---
    st.subheader("Incremental Customers by Investment Tier")
    cust_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#10b981").encode(
        x=alt.X("Tier:N", sort=tier_order, title="Tier"),
        y=alt.Y("Customers Min:Q", title="Incremental Customers"),
        y2="Customers Max:Q",
    )
    cust_line = alt.Chart(chart_df).mark_line(point=True, color="#10b981", strokeWidth=2.5).encode(
        x=alt.X("Tier:N", sort=tier_order),
        y=alt.Y("Customers Midpoint:Q", title="Incremental Customers"),
        tooltip=["Tier", "Customers Min", "Customers Midpoint", "Customers Max", "Investment"],
    )
    st.altair_chart(
        (cust_band + cust_line).properties(title="Customer growth flattens beyond Sustainable Scale (decay curve effect)", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 4: Incremental Revenue across all tiers ---
    st.subheader("Incremental Revenue by Investment Tier")
    rev_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#8b5cf6").encode(
        x=alt.X("Tier:N", sort=tier_order, title="Tier"),
        y=alt.Y("Revenue Min:Q", title="Incremental Revenue ($)"),
        y2="Revenue Max:Q",
    )
    rev_line = alt.Chart(chart_df).mark_line(point=True, color="#8b5cf6", strokeWidth=2.5).encode(
        x=alt.X("Tier:N", sort=tier_order),
        y=alt.Y("Revenue Midpoint:Q", title="Incremental Revenue ($)"),
        tooltip=["Tier", "Revenue Min", "Revenue Midpoint", "Revenue Max", alt.Tooltip("Investment:Q", format="$,.0f")],
    )
    st.altair_chart(
        (rev_band + rev_line).properties(title="Revenue growth mirrors customer decay at higher tiers", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 5: Investment vs Delivered Volume & Prospects (bar chart) ---
    st.subheader("Delivered Volume & Prospects by Tier")
    vol_col, pros_col = st.columns(2)
    vol_chart = alt.Chart(chart_df).mark_bar(color="#06b6d4", opacity=0.8).encode(
        x=alt.X("Tier:N", sort=tier_order, title="Tier"),
        y=alt.Y("Delivered:Q", title="Delivered Volume"),
        tooltip=["Tier", alt.Tooltip("Delivered:Q", format=",.0f"), alt.Tooltip("Investment:Q", format="$,.0f")],
    ).properties(title="Delivered Volume (scales linearly with investment)", height=350)
    vol_col.altair_chart(vol_chart, use_container_width=True)

    pros_chart = alt.Chart(chart_df).mark_bar(color="#f59e0b", opacity=0.8).encode(
        x=alt.X("Tier:N", sort=tier_order, title="Tier"),
        y=alt.Y("Prospects:Q", title="Prospects"),
        tooltip=["Tier", alt.Tooltip("Prospects:Q", format=",.0f"), alt.Tooltip("Investment:Q", format="$,.0f")],
    ).properties(title="Prospects (scales linearly — not curve-affected)", height=350)
    pros_col.altair_chart(pros_chart, use_container_width=True)

    st.divider()

    # --- Chart 6: Investment amount by tier (bar chart) ---
    st.subheader("Investment by Tier")
    chart_df["Tier Type"] = chart_df["Tier"].apply(
        lambda t: "Extension" if "Incremental" in t or "Maximum" in t else "Standard"
    )
    invest_chart = alt.Chart(chart_df).mark_bar(
        cornerRadiusTopLeft=4, cornerRadiusTopRight=4
    ).encode(
        x=alt.X("Tier:N", sort=tier_order, title="Tier"),
        y=alt.Y("Investment:Q", title="Investment ($)"),
        color=alt.Color("Tier Type:N", scale=alt.Scale(
            domain=["Standard", "Extension"], range=["#3b82f6", "#f97316"]
        ), title="Type"),
        tooltip=["Tier", alt.Tooltip("Investment:Q", format="$,.0f"), "Tier Type"],
    ).properties(title="Investment tiers — standard (blue) vs extension (orange)", height=380)
    st.altair_chart(invest_chart, use_container_width=True)

    tab_nav_buttons(tab_names, 4)


# =============================================================================
# TAB 6: ANNUAL & QUARTERLY FORECAST
# =============================================================================
if st.session_state.forecast and active_tab == 5:
    result = st.session_state.forecast
    visible_ranges = [
        row for row in result["ranges"]
        if visible_tier(row.tier_label, result["show_expansion"])
    ]
    visible_projections = [
        row for row in result["projections"]
        if visible_tier(row.tier_label, result["show_expansion"])
    ]
    latest_quarter = max(
        (row["campaign_quarter"] for row in st.session_state.selected_history),
        key=quarter_value,
    )
    upcoming = next_quarter(latest_quarter)

    st.header("Annual & Quarterly Forecast")
    st.caption("Annualized projections and seasonal quarterly/monthly breakdowns for full-year planning.")
    forecast_tabs = st.tabs(["Annual projections", "Quarterly projections", "Monthly breakdown"])

    with forecast_tabs[0]:
        st.markdown("**Annual Projections (x4)**")
        annual_frame = pd.DataFrame([
            {"Tier": row.tier_label, "Annual Investment": float(row.investment) * 4,
             "Delivered": float(row.delivered_volume) * 4, "Prospects": float(row.prospects) * 4,
             "Inc. Customers (Min)": float(row.incremental_customers.minimum) * 4,
             "Inc. Customers (Max)": float(row.incremental_customers.maximum) * 4,
             "Inc. Revenue (Min)": float(row.incremental_revenue.minimum) * 4,
             "Inc. Revenue (Max)": float(row.incremental_revenue.maximum) * 4,
             "CPIx (Min)": float(row.cpix.minimum), "CPIx (Max)": float(row.cpix.maximum),
             "iROAS (Min)": float(row.iroas.minimum), "iROAS (Max)": float(row.iroas.maximum)}
            for row in visible_ranges
        ])
        st.dataframe(annual_frame, hide_index=True, use_container_width=True,
            column_config={col: st.column_config.NumberColumn(format="$%.0f")
                for col in ["Annual Investment", "Inc. Revenue (Min)", "Inc. Revenue (Max)"]})
        for name, factor, rows in result["improvements"]:
            st.markdown(f"**Annual with {name} (+{float(factor)*100:.0f}%)**")
            imp_rows = [{"Tier": r.tier_label, "Annual Investment": float(r.investment)*4,
                "Inc. Customers": float(r.incremental_customers)*4, "Inc. Revenue": float(r.incremental_revenue)*4,
                "CPIx": float(r.cpix), "iROAS": float(r.iroas)}
                for r in rows if r.historical_quarter == latest_quarter and visible_tier(r.tier_label, result["show_expansion"])]
            if imp_rows:
                st.dataframe(pd.DataFrame(imp_rows), hide_index=True, use_container_width=True)

    with forecast_tabs[1]:
        st.markdown("**Quarterly Projections (Q1-Q4)**")
        st.caption("Annual distributed by seasonal organic/incremental indexes.")
        try:
            indexes = seasonal_indexes(session, st.session_state.selected_source, st.session_state.selected_campaign, st.session_state.get("attribution_window", 30))
            for q_num in range(1, 5):
                q_key = f"Q{q_num}"
                o_pct = indexes["quarterly_organic"].get(q_key, 0.25)
                i_pct = indexes["quarterly_incremental"].get(q_key, 0.25)
                st.markdown(f"**{q_key}** (Organic: {o_pct*100:.1f}%, Incremental: {i_pct*100:.1f}%)")
                st.dataframe(pd.DataFrame([
                    {"Tier": row.tier_label, "Investment": float(row.investment)*4*o_pct,
                     "Inc. Customers (Min)": float(row.incremental_customers.minimum)*4*i_pct,
                     "Inc. Customers (Max)": float(row.incremental_customers.maximum)*4*i_pct,
                     "Inc. Revenue (Min)": float(row.incremental_revenue.minimum)*4*i_pct,
                     "Inc. Revenue (Max)": float(row.incremental_revenue.maximum)*4*i_pct}
                    for row in visible_ranges
                ]), hide_index=True, use_container_width=True,
                    column_config={col: st.column_config.NumberColumn(format="$%.0f")
                        for col in ["Investment", "Inc. Revenue (Min)", "Inc. Revenue (Max)"]})
        except Exception as exc:
            st.warning(f"Quarterly projections could not be computed: {exc}")

    with forecast_tabs[2]:
        st.markdown("**Monthly Breakdown (Template Tables 3a & 3b)**")
        try:
            indexes = seasonal_indexes(session, st.session_state.selected_source, st.session_state.selected_campaign, st.session_state.get("attribution_window", 30))
            idx_col1, idx_col2 = st.columns(2)
            with idx_col1:
                st.markdown("**Quarterly indexes**")
                st.dataframe(pd.DataFrame({"Quarter": [f"Q{i}" for i in range(1,5)],
                    "Organic %": [f"{indexes['quarterly_organic'].get(f'Q{i}',0.25)*100:.1f}%" for i in range(1,5)],
                    "Incremental %": [f"{indexes['quarterly_incremental'].get(f'Q{i}',0.25)*100:.1f}%" for i in range(1,5)]}),
                    hide_index=True, use_container_width=True)
            with idx_col2:
                st.markdown("**Monthly indexes**")
                mo_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                st.dataframe(pd.DataFrame({"Month": mo_names,
                    "Organic %": [f"{indexes['monthly_organic'].get(m,1/12)*100:.1f}%" for m in mo_names],
                    "Incremental %": [f"{indexes['monthly_incremental'].get(m,1/12)*100:.1f}%" for m in mo_names]}),
                    hide_index=True, use_container_width=True)

            st.divider()

            from forecast_core import quarterly_monthly_tables
            tables_base = quarterly_monthly_tables(
                visible_ranges, indexes["monthly_organic"], indexes["monthly_incremental"]
            )

            imp_factor = result.get("improvement_factors", {})
            first_factor = next(iter(imp_factor.values()), None) if imp_factor else None
            tables_improved = None
            if first_factor is not None:
                tables_improved = quarterly_monthly_tables(
                    visible_ranges, indexes["monthly_organic"], indexes["monthly_incremental"],
                    improvement_factor=first_factor
                )

            tier_labels = [r.tier_label for r in visible_ranges]
            table_names = {
                "investment": "Monthly Investment Allocations",
                "customers": "Monthly Incremental Customers",
                "revenue": "Monthly Incremental Revenue",
                "cpix": "Monthly CPIx",
                "iroas": "Monthly iROAS",
            }

            monthly_sub_tabs = st.tabs(list(table_names.values()))
            for tab_idx, (table_key, table_title) in enumerate(table_names.items()):
                with monthly_sub_tabs[tab_idx]:
                    for q_num in range(1, 5):
                        rows = tables_base[table_key].get(q_num, [])
                        if not rows:
                            continue
                        cols_to_show = ["month", "index"] + tier_labels
                        df = pd.DataFrame(rows)
                        available_cols = [c for c in cols_to_show if c in df.columns]
                        display_df = df[available_cols].rename(columns={"month": "Month", "index": "Index"})
                        st.dataframe(display_df, hide_index=True, use_container_width=True)

                    if tables_improved:
                        factor_name = next(iter(imp_factor.keys()), "Improvement")
                        factor_val = float(first_factor) * 100
                        st.divider()
                        st.markdown(f"**With {factor_name} (+{factor_val:.0f}%)**")
                        for q_num in range(1, 5):
                            rows = tables_improved[table_key].get(q_num, [])
                            if not rows:
                                continue
                            cols_to_show = ["month", "index"] + tier_labels
                            df = pd.DataFrame(rows)
                            available_cols = [c for c in cols_to_show if c in df.columns]
                            display_df = df[available_cols].rename(columns={"month": "Month", "index": "Index"})
                            st.dataframe(display_df, hide_index=True, use_container_width=True)

        except Exception as exc:
            st.warning(f"Could not compute monthly tables: {exc}")

    tab_nav_buttons(tab_names, 5)