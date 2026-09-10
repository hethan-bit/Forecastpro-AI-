 
     # ForecastPro AI Streamlit app with browser-style tab navigation between workflow steps
# Co-authored with CoCo
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import importlib
import data_access as _data_access
_data_access = importlib.reload(_data_access)
from data_access import (
    active_session,
    account_dimensions,
    resolve_attribution_window,
    historical_preview,
    historical_monthly_preview,
    seasonal_indexes,
    REFERENCE_HISTORICAL_TABLE,
)
from forecast_core import (
    ForecastScenarioInput,
    HistoricalPerformance,
    InvestmentTier,
    apply_improvement_factor,
    calculate_standard_projections,
    forecast_ranges,
    load_curve,
)
from planning_source import planning_input, planning_quarters, PLANNING_INPUT_TABLE


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
  .block-container { padding-top: 0 !important; max-width: 1600px; background: #FAFAFA !important; }

  /* === TYPOGRAPHY — Strong hierarchy === */
  h1 { color: #111111 !important; font-family: 'DM Serif Display', serif !important; font-weight: 400 !important; font-size: 2.2rem !important; letter-spacing: -0.02em !important; line-height: 1.15 !important; margin: 0.15rem 0 0.3rem !important; }
  h2 { color: #111111 !important; font-family: 'Space Grotesk', sans-serif !important; font-weight: 600 !important; font-size: 1.5rem !important; letter-spacing: -0.02em !important; margin: 0.25rem 0 0.35rem !important; }
  h3 { color: #222222 !important; font-family: 'Space Grotesk', sans-serif !important; font-weight: 600 !important; font-size: 1.15rem !important; letter-spacing: -0.01em !important; margin: 0.2rem 0 0.3rem !important; }
  p, span, label, .stMarkdown, [data-testid="stMarkdownContainer"] { color: #333333 !important; }
  .info-icon { display:inline-flex; align-items:center; justify-content:center; width:1rem; height:1rem; margin-left:0.24rem; border:1.4px solid #475569; border-radius:50%; background:#f8fafc; color:#334155 !important; font-family:Arial,sans-serif; font-size:0.68rem; font-weight:700; line-height:1; vertical-align:middle; cursor:help; }
  .info-icon:hover { border-color:#0f766e; background:#ecfdf5; color:#0f766e !important; }

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
    padding: 1rem 1.2rem;
    margin-bottom: 0.45rem;
    min-height: 106px;
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
    padding: 1rem;
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
  hr { border-color: #ECECEC !important; margin: 0.4rem 0 !important; }

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

  /* === TIER ADJUST BUTTONS — compact +/- stacked === */
  [class*="st-key-inc_"],
  [class*="st-key-dec_"] {
    margin-bottom: -0.85rem !important;
    padding: 0 !important;
  }
  [class*="st-key-dec_"] {
    margin-bottom: 0 !important;
  }
  [class*="st-key-inc_"] > button,
  [class*="st-key-dec_"] > button {
    padding: 0.1rem 0.3rem !important;
    font-size: 0.8rem !important;
    min-height: 0 !important;
    height: 26px !important;
    width: 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    margin: 0 auto !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    line-height: 1 !important;
  }
  [class*="st-key-inc_"] > button {
    border-radius: 6px 6px 0 0 !important;
    border-bottom: none !important;
  }
  [class*="st-key-dec_"] > button {
    border-radius: 0 0 6px 6px !important;
  }

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
    background: #0ea65f !important;
    border: 1px solid #0ea65f !important;
    color: #FFFFFF !important;
    border-radius: 12px !important;
  }
  [data-testid="stDownloadButton"] > button:hover {
    background: #07854b !important;
    box-shadow: 0 4px 12px rgba(14,166,95,0.25) !important;
  }

  /* === HELP TOOLTIPS — prevent scrollbar on short text === */
  [data-testid="stTooltipContent"],
  div[data-baseweb="tooltip"] > div,
  div[data-baseweb="popover"] > div > div > div {
    max-height: none !important;
    overflow: visible !important;
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

  /* === HERO HEADER — class-based so Streamlit doesn't strip it === */
  .hero-subtitle {
    color: #999999;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 0 0 0.15rem;
  }
  .hero-subtitle .separator {
    color: #C0C0C0;
    padding: 0 0.4rem;
  }
  .hero-subtitle .product-name {
    letter-spacing: 0.06em;
  }
  .hero-title {
    font-family: 'DM Serif Display', serif !important;
    font-weight: 1000 !important;
    font-size: 3.2rem !important;
    margin: 0 0 0.1rem !important;
    color: #111111 !important;
    letter-spacing: -0.02em !important;
    line-height: 1.15 !important;
  }

  /* === EXTRA SPACING === */
  [data-testid="stVerticalBlock"] > div { margin-bottom: 0.08rem; }
  [data-testid="stHorizontalBlock"] { gap: 0.7rem; }
  [data-testid="stMarkdownContainer"] p { margin: 0.15rem 0 !important; }

  /* === INPUTS WORKFLOW — compact, related controls stay together === */
  .compact-workflow-divider {
    height: 1px;
    background: #ECECEC;
    margin: 0.55rem 0 0.7rem;
  }
  .inputs-intro { margin: 0 0 0.35rem; }
  .inputs-action-row { margin: 0.15rem 0 0.4rem; }

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


def render_mailops_editor(session) -> None:
    """Full-page editor for the FORECASTING_INPUTS planning table."""
    st.markdown(
        '<h1 class="hero-title">Edit MailOps Data</h1>',
        unsafe_allow_html=True,
    )
    if st.button("Back to Forecast Engine", key="_mailops_back"):
        st.session_state.mailops_mode = False
        st.rerun()

    st.markdown('<div class="compact-workflow-divider"></div>', unsafe_allow_html=True)

    # --- Cascading filters sourced from the measurement table ---
    _mo_accounts = sorted({
        str(r["ACCT_NAME"]).strip()
        for r in session.sql(
            f"SELECT DISTINCT ACCT_NAME FROM {REFERENCE_HISTORICAL_TABLE} WHERE ACCT_NAME IS NOT NULL ORDER BY ACCT_NAME"
        ).collect()
        if r["ACCT_NAME"]
    })
    _mo_account = st.selectbox("Client Name", ["(select)"] + _mo_accounts, key="_mo_account")
    if _mo_account == "(select)":
        st.info("Select an account to begin editing.")
        return

    _mo_subs = sorted({
        str(r["SUB_ACCOUNT"]).strip()
        for r in session.sql(
            f"SELECT DISTINCT SUB_ACCOUNT FROM {REFERENCE_HISTORICAL_TABLE} WHERE UPPER(TRIM(ACCT_NAME))=UPPER(TRIM(?)) AND SUB_ACCOUNT IS NOT NULL",
            params=[_mo_account],
        ).collect()
        if r["SUB_ACCOUNT"]
    })
    _mo_channels = sorted({
        str(r["CHANNEL"]).strip()
        for r in session.sql(
            f"SELECT DISTINCT CHANNEL FROM {REFERENCE_HISTORICAL_TABLE} WHERE UPPER(TRIM(ACCT_NAME))=UPPER(TRIM(?)) AND CHANNEL IS NOT NULL",
            params=[_mo_account],
        ).collect()
        if r["CHANNEL"]
    })

    row1 = st.columns(3)
    with row1[0]:
        _mo_sub = st.selectbox("Campaign Name", _mo_subs or ["(none)"], key="_mo_sub")
    with row1[1]:
        _mo_channel = st.selectbox("Marketing Channel", _mo_channels or ["(none)"], key="_mo_channel")

    # Quarters come from the planning table AND test table for this account/sub/channel combo
    _MAILOPS_TEST_TABLE = "ZX.ANALYTICS.FORECASTING_INPUTS_TEST"
    _mo_filter_params = [_mo_account, _mo_sub if _mo_sub != "(none)" else "", _mo_channel if _mo_channel != "(none)" else ""]
    _mo_quarters = sorted({
        str(r["QUARTER"]).strip()
        for r in session.sql(
            f"""SELECT DISTINCT QUARTER FROM (
                    SELECT QUARTER FROM {PLANNING_INPUT_TABLE}
                    WHERE UPPER(TRIM(ACCOUNT_NAME))=UPPER(TRIM(?))
                      AND UPPER(TRIM(COALESCE(SUB_ACCOUNT,'')))=UPPER(TRIM(?))
                      AND UPPER(TRIM(COALESCE(CHANNEL,'')))=UPPER(TRIM(?))
                      AND QUARTER IS NOT NULL
                    UNION
                    SELECT QUARTER FROM {_MAILOPS_TEST_TABLE}
                    WHERE UPPER(TRIM(ACCOUNT_NAME))=UPPER(TRIM(?))
                      AND UPPER(TRIM(COALESCE(SUB_ACCOUNT,'')))=UPPER(TRIM(?))
                      AND UPPER(TRIM(COALESCE(CHANNEL,'')))=UPPER(TRIM(?))
                      AND QUARTER IS NOT NULL
                )""",
            params=_mo_filter_params + _mo_filter_params,
        ).collect()
        if r["QUARTER"]
    })

    def _next_q(q_label: str) -> str:
        import re as _re_nq
        m = _re_nq.match(r"Q(\d)\s+(\d{4})", q_label.strip())
        if not m:
            return ""
        q, y = int(m.group(1)), int(m.group(2))
        return f"Q1 {y + 1}" if q == 4 else f"Q{q + 1} {y}"

    def _quarter_sort_key(label: str) -> int:
        import re as _re_qs
        m = _re_qs.match(r"Q(\d)\s+(\d{4})", label.strip())
        return int(m.group(2)) * 4 + int(m.group(1)) if m else 0

    _mo_quarters_sorted = sorted(_mo_quarters, key=_quarter_sort_key, reverse=True)

    # Compute a next-quarter option from the most recent existing quarter,
    # or from today's date if no planning data exists yet for this combo.
    if _mo_quarters_sorted:
        _nq_label = _next_q(_mo_quarters_sorted[0])
    else:
        from datetime import date as _date_nq
        _today = _date_nq.today()
        _cur_q = (_today.month - 1) // 3 + 1
        _nq_label = f"Q{_cur_q} {_today.year}"

    if _nq_label and _nq_label not in _mo_quarters:
        _mo_quarter_options = [f"{_nq_label} (new)"] + _mo_quarters_sorted
    else:
        _mo_quarter_options = _mo_quarters_sorted

    with row1[2]:
        _mo_quarter = st.selectbox("Input Quarter", _mo_quarter_options or ["(none)"], key="_mo_quarter")

    _is_new_quarter = _mo_quarter.endswith(" (new)")
    _mo_quarter_clean = _mo_quarter.replace(" (new)", "") if _is_new_quarter else _mo_quarter

    if _mo_sub == "(none)" or _mo_channel == "(none)" or _mo_quarter == "(none)":
        st.info("Complete the filters above to load an existing row.")
        return

    # --- Load the reference row: TEST table first, then planning table fallback ---
    _ZERO_COLS = {"CAMPAIGN_BUDGET", "CPM", "IMPRESSIONS", "PLANNED_CAMPAIGN_REACH",
                  "MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE", "SIGNAL_UTILIZATION", "FREQUENCY"}
    _EMPTY_ROW = {
        "QUARTER": _mo_quarter_clean,
        "ACCOUNT_NAME": _mo_account,
        "SUB_ACCOUNT": _mo_sub if _mo_sub != "(none)" else "",
        "CHANNEL": _mo_channel if _mo_channel != "(none)" else "",
        "CAMPAIGN_BUDGET": 0.0, "KPI_GOAL": "", "KPI_TYPE": "", "KPI_TARGET_VALUE": 0.0,
        "CPM": 0.0, "IMPRESSIONS": 0.0, "PLANNED_CAMPAIGN_REACH": 0.0,
        "MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE": 0.0, "SIGNAL_UTILIZATION": 0.0, "FREQUENCY": 0.0,
        "SUBMITTED_BY": "",
    }

    if _is_new_quarter and _mo_quarters_sorted:
        _ref_quarter = _mo_quarters_sorted[0]
    elif not _is_new_quarter:
        _ref_quarter = _mo_quarter_clean
    else:
        _ref_quarter = None

    _mo_row = None
    _has_planning_row = False
    _source_table = ""

    # For non-new quarters, check the test table first
    if _ref_quarter and not _is_new_quarter:
        _test_rows = session.sql(
            f"""SELECT * FROM {_MAILOPS_TEST_TABLE}
                WHERE UPPER(TRIM(QUARTER))=UPPER(TRIM(?))
                  AND UPPER(TRIM(ACCOUNT_NAME))=UPPER(TRIM(?))
                  AND UPPER(TRIM(COALESCE(SUB_ACCOUNT,'')))=UPPER(TRIM(?))
                  AND UPPER(TRIM(COALESCE(CHANNEL,'')))=UPPER(TRIM(?))
                ORDER BY UPDATED_AT DESC NULLS LAST
                LIMIT 1""",
            params=[_ref_quarter, _mo_account, _mo_sub, _mo_channel],
        ).collect()
        if _test_rows:
            _mo_row = _test_rows[0].as_dict()
            _has_planning_row = True
            _source_table = "test"

    # Fall back to planning table
    if _mo_row is None and _ref_quarter:
        _plan_rows = session.sql(
            f"""SELECT * FROM {PLANNING_INPUT_TABLE}
                WHERE UPPER(TRIM(QUARTER))=UPPER(TRIM(?))
                  AND UPPER(TRIM(ACCOUNT_NAME))=UPPER(TRIM(?))
                  AND UPPER(TRIM(COALESCE(SUB_ACCOUNT,'')))=UPPER(TRIM(?))
                  AND UPPER(TRIM(COALESCE(CHANNEL,'')))=UPPER(TRIM(?))""",
            params=[_ref_quarter, _mo_account, _mo_sub, _mo_channel],
        ).collect()
        if _plan_rows:
            _mo_row = _plan_rows[0].as_dict()
            if _is_new_quarter:
                _mo_row["QUARTER"] = _mo_quarter_clean
                for c in _ZERO_COLS:
                    _mo_row[c] = 0.0
            else:
                _has_planning_row = True
            _source_table = "planning"

    if _mo_row is None:
        _mo_row = _EMPTY_ROW
    _ALL_COLS = [
        "QUARTER", "ACCOUNT_NAME", "SUB_ACCOUNT", "CHANNEL",
        "CAMPAIGN_BUDGET", "KPI_TYPE", "KPI_TARGET_VALUE",
        "CPM", "IMPRESSIONS", "PLANNED_CAMPAIGN_REACH",
        "MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE", "SIGNAL_UTILIZATION", "FREQUENCY",
    ]
    _KEY_COLS = {"QUARTER", "ACCOUNT_NAME", "SUB_ACCOUNT", "CHANNEL"}
    _STR_COLS = {"QUARTER", "ACCOUNT_NAME", "SUB_ACCOUNT", "CHANNEL", "KPI_TYPE"}

    _COL_RENAME = {
        "QUARTER": "Quarter",
        "ACCOUNT_NAME": "Client Name",
        "SUB_ACCOUNT": "Campaign Name",
        "CHANNEL": "Marketing Channel",
        "CAMPAIGN_BUDGET": "Budget",
        "KPI_TYPE": "KPI Type",
        "KPI_TARGET_VALUE": "KPI Target",
        "CPM": "CPM",
        "IMPRESSIONS": "Impressions",
        "PLANNED_CAMPAIGN_REACH": "Planned Reach",
        "MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE": "Max Reach",
        "SIGNAL_UTILIZATION": "Signal Util.",
        "FREQUENCY": "Frequency",
    }
    _ROW1_COLS = ["QUARTER", "ACCOUNT_NAME", "SUB_ACCOUNT", "CHANNEL",
                  "CAMPAIGN_BUDGET", "KPI_TYPE", "KPI_TARGET_VALUE"]
    _ROW2_COLS = ["CPM", "IMPRESSIONS", "PLANNED_CAMPAIGN_REACH",
                  "MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE", "SIGNAL_UTILIZATION", "FREQUENCY"]

    def _build_row(cols):
        return {_COL_RENAME[c]: (str(_mo_row[c]) if _mo_row[c] is not None else "") if c in _STR_COLS
                else (float(_mo_row[c]) if _mo_row[c] is not None else 0.0)
                for c in cols}

    _df1 = pd.DataFrame([_build_row(_ROW1_COLS)])
    _df2 = pd.DataFrame([_build_row(_ROW2_COLS)])
    _DISPLAY_KEY_COLS = {_COL_RENAME[c] for c in _KEY_COLS}

    if not _has_planning_row and _is_new_quarter and _ref_quarter:
        st.subheader(f"New {_mo_quarter_clean} — edit values below")
        st.caption(f"KPI Type and KPI Target carried over from {_ref_quarter}. Other fields start at zero.")
    elif not _has_planning_row:
        st.subheader(f"New row for {_mo_quarter_clean} — no existing planning data")
        st.caption("This client/campaign/channel combination has no planning data yet. Fill in the values below.")
    else:
        st.subheader("Current row — edit values below")
        _submitted = _mo_row.get("SUBMITTED_BY", "") or ""
        _updated = _mo_row.get("UPDATED_AT", "") or ""
        if _submitted:
            st.caption(f"Last saved by **{_submitted}**" + (f" at {_updated} UTC" if _updated else ""))
    _edited1 = st.data_editor(
        _df1,
        hide_index=True,
        use_container_width=True,
        disabled=list(_DISPLAY_KEY_COLS),
        key="_mo_editor_1",
        column_config={
            "Budget": st.column_config.NumberColumn(format="%.2f"),
            "KPI Target": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    _edited2 = st.data_editor(
        _df2,
        hide_index=True,
        use_container_width=True,
        key="_mo_editor_2",
        column_config={
            "CPM": st.column_config.NumberColumn(format="%.2f"),
            "Impressions": st.column_config.NumberColumn(format="%.0f"),
            "Planned Reach": st.column_config.NumberColumn(format="%.0f"),
            "Max Reach": st.column_config.NumberColumn(format="%.0f"),
            "Signal Util.": st.column_config.NumberColumn(format="%.2f"),
            "Frequency": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    if st.button("Save as New Row", type="primary", key="_mo_save"):
        try:
            new1 = _edited1.iloc[0]
            new2 = _edited2.iloc[0]
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            _current_user = session.sql("SELECT CURRENT_USER()").collect()[0][0]
            session.sql(
                f"""INSERT INTO {_MAILOPS_TEST_TABLE}
                    (QUARTER, ACCOUNT_NAME, SUB_ACCOUNT, CHANNEL,
                     CAMPAIGN_BUDGET, KPI_GOAL, KPI_TYPE, KPI_TARGET_VALUE,
                     CPM, IMPRESSIONS, PLANNED_CAMPAIGN_REACH,
                     MAXIMUM_REACH_TO_MAINTAIN_PERFORMANCE, SIGNAL_UTILIZATION, FREQUENCY,
                     UPDATED_AT, SUBMITTED_BY)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                params=[
                    str(new1["Quarter"]),
                    str(new1["Client Name"]),
                    str(new1["Campaign Name"]),
                    str(new1["Marketing Channel"]),
                    float(new1["Budget"]),
                    str(_mo_row.get("KPI_GOAL", "") or ""),
                    str(new1["KPI Type"]),
                    float(new1["KPI Target"]),
                    float(new2["CPM"]),
                    float(new2["Impressions"]),
                    float(new2["Planned Reach"]),
                    float(new2["Max Reach"]),
                    float(new2["Signal Util."]),
                    float(new2["Frequency"]),
                    now_utc,
                    _current_user,
                ],
            ).collect()
            st.success(f"Row saved by {_current_user} at {now_utc} UTC.")
            st.rerun()
        except Exception as exc:
            st.error(f"Save failed: {exc}")




def initialize_state() -> None:
    defaults = {
        "sources": [],
        "preview": [],
        "confirmed": False,
        "forecast": None,
        "planning_campaigns": [],
        "message": "Select historical inputs to begin.",
        "source_account": None,
        "current_budget": 1_279_611.0,
        "cpm": 8.5,
        "planned_reach": 7_923_287.93,
        "signal_utilization": 1.0,
        "max_reach": 10_000_000.0,
        "frequency_at_max": 18.0,
        "selected_source": None,
        "historical_scope_label": "Historical slice",
        "selected_sub_account": None,
        "selected_event": None,
        "selected_channel": None,
        "projection_mode": "Quarterly",
        "projection_quarter": None,
        "monthly_history": [],
        "monthly_index_mode": "Automatic",
        "manual_monthly_organic": {},
        "manual_monthly_incremental": {},
        "monthly_index_signature": None,
        "scroll_to_top": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def get_session():
    """Get the Snowflake session. Always fresh from the platform — no caching."""
    return active_session()


def reset_for_new_account() -> None:
    """Clear all app state so user can start fresh with a new account."""
    keys_to_clear = [
        "sources", "preview", "confirmed", "forecast",
        "planning_campaigns", "message", "source_account",
        "current_budget", "cpm", "planned_reach", "signal_utilization",
        "max_reach", "frequency_at_max", "_widget_frequency_at_max", "selected_source",
        "historical_scope_label", "selected_history", "tier_overrides",
        "show_historical_kpis",
        "applied_planning_key", "active_tab", "num_scenarios",
        "attribution_window", "selected_sub_account", "selected_event",
        "selected_channel", "selected_planning_quarter",
        "planning_quarter_scope", "monthly_index_mode",
        "manual_monthly_organic", "manual_monthly_incremental",
        "monthly_index_signature",
        "_widget_all_account", "_widget_sub_account", "_widget_event",
        "_widget_channel", "input_selection_signature",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)


def reset_after_source() -> None:
    st.session_state.pop("_widget_selected_source_v2", None)
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
        "monthly_index_mode",
        "manual_monthly_organic",
        "manual_monthly_incremental",
        "monthly_index_signature",
    ):
        st.session_state.pop(key, None)


def clear_downstream_input_state() -> None:
    """Invalidate a loaded slice when any of its four identifying inputs changes."""
    st.session_state.preview = []
    st.session_state.monthly_history = []
    st.session_state.confirmed = False
    st.session_state.forecast = None
    st.session_state.pop("selected_history", None)
    st.session_state.pop("selected_planning_quarter", None)
    st.session_state.pop("planning_quarter_scope", None)
    st.session_state.pop("applied_planning_key", None)


def money(value) -> str:
    return f"${float(value):,.0f}"


def number(value) -> str:
    return f"{float(value):,.0f}"


def _fmt_dollar_commas(v: float) -> str:
    return f"${v:,.0f}"

def _fmt_compact_k(v: float) -> str:
    abs_v = abs(v)
    if abs_v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    elif abs_v >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:.0f}"

def _fmt_dollar_compact_m(v: float) -> str:
    abs_v = abs(v)
    if abs_v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    elif abs_v >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.0f}"

def _fmt_dollar_0(v: float) -> str:
    return f"${v:,.0f}"

def _fmt_iroas(v: float) -> str:
    return f"${v:,.2f}"

def _range_str(lo: float, hi: float, fmt_func) -> str:
    if abs(lo - hi) < 0.005:
        return fmt_func(lo)
    return f"{fmt_func(lo)} - {fmt_func(hi)}"


MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
QUARTER_MONTHS = {
    "Q1": ("Jan", "Feb", "Mar"),
    "Q2": ("Apr", "May", "Jun"),
    "Q3": ("Jul", "Aug", "Sep"),
    "Q4": ("Oct", "Nov", "Dec"),
}


def effective_monthly_indexes(automatic_indexes: dict) -> dict:
    """Use manual monthly weights only after the analyst opts into Manual mode."""
    indexes = {
        **automatic_indexes,
        "monthly_organic": dict(automatic_indexes["monthly_organic"]),
        "monthly_incremental": dict(automatic_indexes["monthly_incremental"]),
        "quarterly_organic": dict(automatic_indexes["quarterly_organic"]),
        "quarterly_incremental": dict(automatic_indexes["quarterly_incremental"]),
    }
    if st.session_state.get("monthly_index_mode", "Automatic") != "Manual":
        return indexes

    organic = st.session_state.get("manual_monthly_organic", {})
    incremental = st.session_state.get("manual_monthly_incremental", {})
    if set(organic) != set(MONTH_NAMES) or set(incremental) != set(MONTH_NAMES):
        return indexes

    indexes["monthly_organic"] = {month: float(organic[month]) for month in MONTH_NAMES}
    indexes["monthly_incremental"] = {
        month: float(incremental[month]) for month in MONTH_NAMES
    }
    expected_quarters = {f"Q{i}" for i in range(1, 5)}
    manual_quarterly_organic = st.session_state.get("manual_quarterly_organic", {})
    manual_quarterly_incremental = st.session_state.get("manual_quarterly_incremental", {})
    if (
        set(manual_quarterly_organic) == expected_quarters
        and set(manual_quarterly_incremental) == expected_quarters
    ):
        indexes["quarterly_organic"] = {
            quarter: float(manual_quarterly_organic[quarter])
            for quarter in expected_quarters
        }
        indexes["quarterly_incremental"] = {
            quarter: float(manual_quarterly_incremental[quarter])
            for quarter in expected_quarters
        }
    else:
        indexes["quarterly_organic"] = {
            quarter: sum(indexes["monthly_organic"][month] for month in months)
            for quarter, months in QUARTER_MONTHS.items()
        }
        indexes["quarterly_incremental"] = {
            quarter: sum(indexes["monthly_incremental"][month] for month in months)
            for quarter, months in QUARTER_MONTHS.items()
        }
    return indexes


def manual_seasonal_indexes_valid() -> bool:
    """Manual seasonal allocations must total exactly 100% for every table."""
    if st.session_state.get("monthly_index_mode", "Automatic") != "Manual":
        return True
    required = (
        (st.session_state.get("manual_monthly_organic", {}), set(MONTH_NAMES)),
        (st.session_state.get("manual_monthly_incremental", {}), set(MONTH_NAMES)),
        (st.session_state.get("manual_quarterly_organic", {}), {f"Q{i}" for i in range(1, 5)}),
        (st.session_state.get("manual_quarterly_incremental", {}), {f"Q{i}" for i in range(1, 5)}),
    )
    return all(
        set(values) == expected and abs(sum(float(value) for value in values.values()) - 1.0) < 0.00001
        for values, expected in required
    )


def render_monthly_index_section(automatic_indexes: dict) -> dict:
    """Render compact automatic/manual seasonal-index tables and return their weights."""
    signature = (
        st.session_state.get("source_account"),
        st.session_state.get("selected_sub_account"),
        st.session_state.get("selected_event"),
        st.session_state.get("selected_channel"),
        st.session_state.get("attribution_window", 30),
    )
    if st.session_state.get("monthly_index_signature") != signature:
        st.session_state.monthly_index_mode = "Automatic"
        st.session_state.manual_monthly_organic = {}
        st.session_state.manual_monthly_incremental = {}
        st.session_state.manual_quarterly_organic = {}
        st.session_state.manual_quarterly_incremental = {}
        st.session_state.monthly_index_signature = signature

    st.markdown("### Seasonal Indexes: Quarterly & Monthly Conversions")
    st.caption("Seasonal indexes reflect trends in gross client conversions and Zeta-influenced conversions.")
    mode_col, reset_col, _ = st.columns([2, 1.4, 5])
    def _reset_monthly_indexes():
        st.session_state.monthly_index_mode = "Automatic"
        st.session_state.manual_monthly_organic = {}
        st.session_state.manual_monthly_incremental = {}
        st.session_state.forecast = None
        st.session_state.message = "Monthly indexes reset to their automatic values."

    with mode_col:
        st.radio(
            "Index mode",
            ("Automatic", "Manual"),
            horizontal=True,
            key="monthly_index_mode",
            help="Automatic uses the calculated indexes. Manual lets you edit the same Quarterly and Monthly tables used by the forecast.",
        )
    with reset_col:
        st.button(
            "↺ Reset to Automatic",
            key="reset_monthly_indexes",
            disabled=st.session_state.monthly_index_mode == "Automatic",
            on_click=_reset_monthly_indexes,
        )

    quarters = [f"Q{i}" for i in range(1, 5)]
    if st.session_state.monthly_index_mode == "Manual":
        if not st.session_state.manual_monthly_organic:
            st.session_state.manual_monthly_organic = {
                month: float(automatic_indexes["monthly_organic"].get(month, 0.0))
                for month in MONTH_NAMES
            }
            st.session_state.manual_monthly_incremental = {
                month: float(automatic_indexes["monthly_incremental"].get(month, 0.0))
                for month in MONTH_NAMES
            }
        if not st.session_state.manual_quarterly_organic:
            st.session_state.manual_quarterly_organic = {
                quarter: float(automatic_indexes["quarterly_organic"].get(quarter, 0.0))
                for quarter in quarters
            }
            st.session_state.manual_quarterly_incremental = {
                quarter: float(automatic_indexes["quarterly_incremental"].get(quarter, 0.0))
                for quarter in quarters
            }
        quarterly_organic = st.session_state.manual_quarterly_organic
        quarterly_incremental = st.session_state.manual_quarterly_incremental
        monthly_organic = st.session_state.manual_monthly_organic
        monthly_incremental = st.session_state.manual_monthly_incremental
    else:
        indexes = effective_monthly_indexes(automatic_indexes)
        quarterly_organic = indexes["quarterly_organic"]
        quarterly_incremental = indexes["quarterly_incremental"]
        monthly_organic = indexes["monthly_organic"]
        monthly_incremental = indexes["monthly_incremental"]

    st.markdown("**Quarterly Seasonal Indexes**")
    st.caption("Organic and Incremental values must each sum to 100%.")
    quarterly_frame = pd.DataFrame(
        {
            "Quarter": quarters,
            "Organic %": [quarterly_organic.get(quarter, 0.0) * 100 for quarter in quarters],
            "Incremental %": [quarterly_incremental.get(quarter, 0.0) * 100 for quarter in quarters],
        }
    )
    if st.session_state.monthly_index_mode == "Manual":
        quarterly_edited = st.data_editor(
            quarterly_frame,
            hide_index=True,
            use_container_width=True,
            disabled=["Quarter"],
            key="quarterly_seasonal_index_editor",
            column_config={
                "Organic %": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%.1f%%"),
                "Incremental %": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%.1f%%"),
            },
        )
        new_quarterly_organic = {
            row["Quarter"]: float(row["Organic %"]) / 100 for _, row in quarterly_edited.iterrows()
        }
        new_quarterly_incremental = {
            row["Quarter"]: float(row["Incremental %"]) / 100 for _, row in quarterly_edited.iterrows()
        }
        if (
            new_quarterly_organic != st.session_state.manual_quarterly_organic
            or new_quarterly_incremental != st.session_state.manual_quarterly_incremental
        ):
            st.session_state.manual_quarterly_organic = new_quarterly_organic
            st.session_state.manual_quarterly_incremental = new_quarterly_incremental
            st.session_state.forecast = None
            st.session_state.message = "Quarterly seasonal indexes changed. Create a new forecast draft to update results."
    else:
        st.dataframe(quarterly_frame, hide_index=True, use_container_width=True)

    st.markdown("**Monthly Seasonal Indexes**")
    st.caption("Organic and Incremental values must each sum to 100%.")
    monthly_frame = pd.DataFrame(
        [
            {"Metric": "Organic %", **{month: monthly_organic.get(month, 0.0) * 100 for month in MONTH_NAMES},
             "Total": sum(monthly_organic.values()) * 100},
            {"Metric": "Incremental %", **{month: monthly_incremental.get(month, 0.0) * 100 for month in MONTH_NAMES},
             "Total": sum(monthly_incremental.values()) * 100},
        ]
    )
    monthly_columns = {
        month: st.column_config.NumberColumn(min_value=0.0, step=0.1, format="%.1f%%")
        for month in MONTH_NAMES
    }
    monthly_columns["Total"] = st.column_config.NumberColumn(format="%.1f%%")
    if st.session_state.monthly_index_mode == "Manual":
        monthly_edited = st.data_editor(
            monthly_frame,
            hide_index=True,
            use_container_width=True,
            disabled=["Metric", "Total"],
            key="monthly_seasonal_index_editor",
            column_config=monthly_columns,
        )
        new_monthly_organic = {
            month: float(monthly_edited.loc[monthly_edited["Metric"] == "Organic %", month].iloc[0]) / 100
            for month in MONTH_NAMES
        }
        new_monthly_incremental = {
            month: float(monthly_edited.loc[monthly_edited["Metric"] == "Incremental %", month].iloc[0]) / 100
            for month in MONTH_NAMES
        }
        if (
            new_monthly_organic != st.session_state.manual_monthly_organic
            or new_monthly_incremental != st.session_state.manual_monthly_incremental
        ):
            st.session_state.manual_monthly_organic = new_monthly_organic
            st.session_state.manual_monthly_incremental = new_monthly_incremental
            st.session_state.forecast = None
            st.session_state.message = "Monthly seasonal indexes changed. Create a new forecast draft to update results."
        totals = {
            "Quarterly organic": sum(st.session_state.manual_quarterly_organic.values()) * 100,
            "Quarterly incremental": sum(st.session_state.manual_quarterly_incremental.values()) * 100,
            "Monthly organic": sum(st.session_state.manual_monthly_organic.values()) * 100,
            "Monthly incremental": sum(st.session_state.manual_monthly_incremental.values()) * 100,
        }
        st.caption(" | ".join(f"{label}: {total:.1f}%" for label, total in totals.items()))
        if not manual_seasonal_indexes_valid():
            st.error("Manual seasonal indexes must each total exactly 100% before you create a forecast.")
    else:
        st.dataframe(monthly_frame, hide_index=True, use_container_width=True, column_config=monthly_columns)

    return effective_monthly_indexes(automatic_indexes)


def quarter_value(label: str) -> int:
    match = re.fullmatch(r"Q([1-4])\s+(\d{4})", label.strip(), re.I)
    return int(match.group(2)) * 4 + int(match.group(1)) if match else 0


def next_quarter(label: str) -> str:
    match = re.fullmatch(r"Q([1-4])\s+(\d{4})", label.strip(), re.I)
    if not match:
        return "Upcoming quarter"
    quarter, year = int(match.group(1)), int(match.group(2))
    return f"Q1 {year + 1}" if quarter == 4 else f"Q{quarter + 1} {year}"


def rolling_quarters(start_label: str) -> list[str]:
    """Return 4 quarter labels starting from start_label (e.g. Q3 2026 -> Q3 2026, Q4 2026, Q1 2027, Q2 2027)."""
    labels = [start_label]
    cur = start_label
    for _ in range(3):
        cur = next_quarter(cur)
        labels.append(cur)
    return labels


def visible_tier(label: str, show_expansion: bool) -> bool:
    if label.startswith("Extended Scale"):
        return False
    return show_expansion or not (
        label.startswith("Market Expansion")
        or label.startswith("Strategic Scale")
        or label.startswith("Optimal Scale")
    )


def scroll_page_to_top() -> None:
    """Reset the Streamlit main viewport after tab navigation."""
    components.html(
        """
        <script>
        const scrollToTop = () => {
          const main = window.parent.document.querySelector(
            'section[data-testid="stMain"]'
          );
          if (main) {
            main.scrollTop = 0;
            main.scrollTo({top: 0, left: 0, behavior: 'auto'});
          }
        };
        scrollToTop();
        window.parent.setTimeout(scrollToTop, 50);
        window.parent.setTimeout(scrollToTop, 250);
        </script>
        """,
        height=0,
        width=0,
    )


def _render_download_button(key_suffix: str, chart_images: list[tuple[str, bytes]] | None = None) -> None:
    """Build xlsx inline and render download button."""
    import io as _io
    import zipfile as _zf
    from xml.sax.saxutils import escape as _esc
    from collections import defaultdict as _dd

    result = st.session_state.get("forecast")
    if not result:
        return
    vis_ranges = [r for r in result["ranges"] if visible_tier(r.tier_label, result["show_expansion"])]
    history = st.session_state.selected_history
    improvements = result["improvements"]
    indexes = st.session_state.get("_cached_indexes")
    proj_mode = st.session_state.get("projection_mode", "Quarterly")
    proj_quarter = st.session_state.get("projection_quarter", "")
    account = st.session_state.source_account
    first_tier = vis_ranges[0].tier_label if vis_ranges else ""
    sig_util = st.session_state.get("_cached_sig_util", {})

    def fmoney(v): return f"${v:,.0f}"
    def fint(v): return f"{v:,.0f}"
    def firoas(v): return f"${v:,.2f}"
    def fk(v):
        a = abs(v)
        if a >= 1e6: return f"{v/1e6:.1f}M"
        if a >= 1e3: return f"{v/1e3:.1f}K"
        return f"{v:.0f}"
    def fdk(v):
        a = abs(v)
        if a >= 1e6: return f"${v/1e6:.1f}M"
        if a >= 1e3: return f"${v/1e3:.1f}K"
        return f"${v:.0f}"
    def rng(lo, hi, fmt):
        if abs(lo - hi) < 0.005: return fmt(lo)
        return f"{fmt(lo)} - {fmt(hi)}"

    # --- Build sheets as list-of-lists (header + data rows) ---
    sheets = {}

    # Tab 1: Historical KPIs
    h_header = ["Quarter", "Delivered", "Spend", "Avg Frequency", "Prospects",
                "Inc Customers", "Inc Revenue", "Avg Inc Rev", "CPIx", "iROAS"]
    h_rows = [h_header]
    for r in history:
        h_rows.append([r["campaign_quarter"], fint(float(r["delivered_volume"])),
            fmoney(float(r["source_spend"])), f"{float(r['frequency']):.1f}",
            fint(float(r["prospects"])), fint(float(r["incremental_customers"])),
            fmoney(float(r["incremental_revenue"])), fmoney(float(r["average_incremental_revenue"])),
            fmoney(float(r["cpix"])), firoas(float(r["iroas"]))])
    if history:
        n = len(history)
        av = lambda f: sum(float(x[f]) for x in history) / n
        h_rows.append(["Average", fint(av("delivered_volume")), fmoney(av("source_spend")),
            f"{av('frequency'):.1f}", fint(av("prospects")), fint(av("incremental_customers")),
            fmoney(av("incremental_revenue")), fmoney(av("average_incremental_revenue")),
            fmoney(av("cpix")), firoas(av("iroas"))])
    sheets["Historical KPIs"] = h_rows

    # Tab 2: Forecast (matches 3a UI exactly)
    f_header = ["Tier", "Investment Tier", "Delivered Volume", "# of Prospects",
                "Inc. Customers", "Incremental Revenue", "CPIx", "iROAS",
                "Marginal CPIx", "Marginal iROAS", "Signal Utilization"]
    nc = len(f_header)
    is_annual = proj_mode != "Quarterly"
    mult = 4 if is_annual else 1
    label = "Annual" if is_annual else proj_quarter
    forecast_sheet_name = "Annual Forecast" if is_annual else "Quarterly Forecast"
    f_rows = [f_header]
    f_rows.append([f"Baseline ({label})"] + [""] * (nc - 1))
    for r in vis_ranges:
        f_rows.append([
            r.tier_label, fmoney(float(r.investment) * mult), fint(float(r.delivered_volume) * mult),
            fint(float(r.prospects) * mult),
            rng(float(r.incremental_customers.minimum) * mult, float(r.incremental_customers.maximum) * mult, fk),
            rng(float(r.incremental_revenue.minimum) * mult, float(r.incremental_revenue.maximum) * mult, fdk),
            rng(float(r.cpix.minimum), float(r.cpix.maximum), fmoney),
            rng(float(r.iroas.minimum), float(r.iroas.maximum), firoas),
            "", "", f"{sig_util.get(r.tier_label, 0):.1f}%"])
    for name, factor, imp_rows in improvements:
        f_rows.append([""] * nc)
        f_rows.append([f"+{float(factor)*100:.0f}% Improvement ({name})"] + [""] * (nc - 1))
        by_tier = _dd(list)
        for ir in imp_rows:
            by_tier[ir.tier_label].append(ir)
        range_map = {r.tier_label: r for r in vis_ranges}
        ra = 0.10
        for tl, trows in by_tier.items():
            rr = range_map.get(tl)
            cs = [float(x.incremental_customers) for x in trows]
            rs = [float(x.incremental_revenue) for x in trows]
            cxs = [float(x.cpix) for x in trows]
            irs = [float(x.iroas) for x in trows]
            mcs = [float(x.marginal_cpix) for x in trows if x.marginal_cpix and x.marginal_cpix > 0]
            mis = [float(x.marginal_iroas) for x in trows if x.marginal_iroas and x.marginal_iroas > 0]
            if len(trows) == 1:
                cr = rng(cs[0]*(1-ra), cs[0]*(1+ra), fk)
                rvr = rng(rs[0]*(1-ra), rs[0]*(1+ra), fdk)
                cxr = rng(cxs[0]/(1+ra), cxs[0]/(1-ra), fmoney)
                irr = rng(irs[0]*(1-ra), irs[0]*(1+ra), firoas)
                mcr = rng(mcs[0]/(1+ra), mcs[0]/(1-ra), fmoney) if mcs else "—"
                mir = rng(mis[0]*(1-ra), mis[0]*(1+ra), firoas) if mis else "—"
            else:
                cr = rng(min(cs), max(cs), fk)
                rvr = rng(min(rs), max(rs), fdk)
                cxr = rng(min(cxs), max(cxs), fmoney)
                irr = rng(min(irs), max(irs), firoas)
                mcr = rng(min(mcs), max(mcs), fmoney) if mcs else "—"
                mir = rng(min(mis), max(mis), firoas) if mis else "—"
            if tl == first_tier:
                mcr = "—"; mir = "—"
            f_rows.append([tl, fmoney(float(trows[0].investment)),
                fint(float(rr.delivered_volume)) if rr else "—",
                fint(float(rr.prospects)) if rr else "—",
                cr, rvr, cxr, irr, mcr, mir, f"{sig_util.get(tl, 0):.1f}%"])
    sheets[forecast_sheet_name] = f_rows

    # Tab 3+: Splits
    QM = {1: ["Jan","Feb","Mar"], 2: ["Apr","May","Jun"], 3: ["Jul","Aug","Sep"], 4: ["Oct","Nov","Dec"]}
    sp_header = ["Tier", "Investment", "Delivered", "Prospects", "Inc. Customers",
                 "Inc. Revenue", "CPIx", "iROAS"]
    snc = len(sp_header)

    def split_rows(vr, op, ip, im=1.0, fac=4):
        out = []
        for r in vr:
            inv = float(r.investment) * fac * op
            cmn = float(r.incremental_customers.minimum) * fac * ip * im
            cmx = float(r.incremental_customers.maximum) * fac * ip * im
            rmn = float(r.incremental_revenue.minimum) * fac * ip * im
            rmx = float(r.incremental_revenue.maximum) * fac * ip * im
            out.append([r.tier_label, fmoney(inv),
                fint(float(r.delivered_volume) * fac * op), fint(float(r.prospects) * fac * op),
                rng(cmn, cmx, fk), rng(rmn, rmx, fdk),
                rng(inv/cmx if cmx > 0 else 0, inv/cmn if cmn > 0 else 0, fmoney),
                rng(rmn/inv if inv > 0 else 0, rmx/inv if inv > 0 else 0, firoas)])
        return out

    def split_vals(vr, op, ip, im=1.0, fac=4):
        """Like split_rows but returns only the 7 data columns (no tier label)."""
        out = []
        for r in vr:
            inv = float(r.investment) * fac * op
            cmn = float(r.incremental_customers.minimum) * fac * ip * im
            cmx = float(r.incremental_customers.maximum) * fac * ip * im
            rmn = float(r.incremental_revenue.minimum) * fac * ip * im
            rmx = float(r.incremental_revenue.maximum) * fac * ip * im
            out.append([fmoney(inv),
                fint(float(r.delivered_volume) * fac * op), fint(float(r.prospects) * fac * op),
                rng(cmn, cmx, fk), rng(rmn, rmx, fdk),
                rng(inv/cmx if cmx > 0 else 0, inv/cmn if cmn > 0 else 0, fmoney),
                rng(rmn/inv if inv > 0 else 0, rmx/inv if inv > 0 else 0, firoas)])
        return out

    _data_cols = ["Investment", "Delivered", "Prospects", "Inc. Customers",
                  "Inc. Revenue", "CPIx", "iROAS"]

    if indexes and vis_ranges:
        if proj_mode == "Quarterly":
            import re as _re_sp
            _m = _re_sp.match(r"Q(\d)\s+(\d{4})", proj_quarter)
            qn = int(_m.group(1)) if _m else 1
            months = QM[qn]
            osum = sum(indexes["monthly_organic"].get(m, 1/12) for m in months)
            isum = sum(indexes["monthly_incremental"].get(m, 1/12) for m in months)
            ms_rows = [sp_header]
            for mo in months:
                op = indexes["monthly_organic"].get(mo, 1/12) / osum if osum else 1/3
                ip = indexes["monthly_incremental"].get(mo, 1/12) / isum if isum else 1/3
                ms_rows.append([mo] + [""] * (snc - 1))
                ms_rows.extend(split_rows(vis_ranges, op, ip, fac=1))
            sheets["Monthly Split"] = ms_rows
        else:
            # Build rolling quarter labels starting from projection quarter
            _rq = rolling_quarters(proj_quarter) if proj_quarter else [f"Q{n}" for n in range(1, 5)]
            # Map rolling quarter label -> seasonal index key (Q1-Q4)
            def _q_key(ql):
                m = re.match(r"Q(\d)", ql)
                return f"Q{m.group(1)}" if m else "Q1"
            # Map rolling quarter label -> month names
            def _q_months(ql):
                m = re.match(r"Q(\d)", ql)
                return QM[int(m.group(1))] if m else QM[1]
            # Extract year from quarter label
            def _q_year(ql):
                m = re.search(r"\d{4}", ql)
                return m.group() if m else ""

            if improvements:
                # --- Annual Quarterly Split: side-by-side scenarios ---
                scenario_row = [""] + ["Baseline"] + [""] * 6
                for nm, fc, _ in improvements:
                    scenario_row += ["", f"+{float(fc)*100:.0f}% ({nm})"] + [""] * 6
                col_row = ["Tier"] + _data_cols
                for _ in improvements:
                    col_row += [""] + _data_cols

                qs_rows = [scenario_row, col_row]
                for ql in _rq:
                    qk = _q_key(ql)
                    o = indexes["quarterly_organic"].get(qk, 0.25)
                    i = indexes["quarterly_incremental"].get(qk, 0.25)
                    total_cols = len(col_row)
                    # Section row: repeat quarter label above each scenario block
                    sec = [ql] + [""] * 7
                    for _ in improvements:
                        sec += ["", ql] + [""] * 6
                    qs_rows.append(sec)
                    base = split_vals(vis_ranges, o, i)
                    imp_data = []
                    for nm, fc, _ in improvements:
                        imp_data.append(split_vals(vis_ranges, o, i, 1 + float(fc)))
                    for ti, r in enumerate(vis_ranges):
                        row = [r.tier_label] + base[ti]
                        for imp_v in imp_data:
                            row += [""] + imp_v[ti]
                        qs_rows.append(row)
                sheets["Quarterly Split"] = qs_rows

                # --- Annual Monthly Split: side-by-side scenarios ---
                ms_rows = [scenario_row, col_row]
                for ql in _rq:
                    qk = _q_key(ql)
                    mos = _q_months(ql)
                    yr = _q_year(ql)
                    qo = indexes["quarterly_organic"].get(qk, 0.25)
                    qi = indexes["quarterly_incremental"].get(qk, 0.25)
                    os2 = sum(indexes["monthly_organic"].get(m, 1/12) for m in mos)
                    is2 = sum(indexes["monthly_incremental"].get(m, 1/12) for m in mos)
                    for mo in mos:
                        op = qo * (indexes["monthly_organic"].get(mo, 1/12) / os2) if os2 else qo / 3
                        ip = qi * (indexes["monthly_incremental"].get(mo, 1/12) / is2) if is2 else qi / 3
                        total_cols = len(col_row)
                        mo_label = f"{mo} {yr}" if yr else mo
                        # Section row: repeat month label above each scenario block
                        sec = [mo_label] + [""] * 7
                        for _ in improvements:
                            sec += ["", mo_label] + [""] * 6
                        ms_rows.append(sec)
                        base = split_vals(vis_ranges, op, ip)
                        imp_data = []
                        for nm, fc, _ in improvements:
                            imp_data.append(split_vals(vis_ranges, op, ip, 1 + float(fc)))
                        for ti, r in enumerate(vis_ranges):
                            row = [r.tier_label] + base[ti]
                            for imp_v in imp_data:
                                row += [""] + imp_v[ti]
                            ms_rows.append(row)
                sheets["Monthly Split"] = ms_rows
            else:
                # No improvements — simple stacked layout
                qs_rows = [sp_header]
                for ql in _rq:
                    qk = _q_key(ql)
                    o = indexes["quarterly_organic"].get(qk, 0.25)
                    i = indexes["quarterly_incremental"].get(qk, 0.25)
                    qs_rows.append([ql] + [""] * (snc - 1))
                    qs_rows.extend(split_rows(vis_ranges, o, i))
                sheets["Quarterly Split"] = qs_rows

                ms_rows = [sp_header]
                for ql in _rq:
                    qk = _q_key(ql)
                    mos = _q_months(ql)
                    yr = _q_year(ql)
                    qo = indexes["quarterly_organic"].get(qk, 0.25)
                    qi = indexes["quarterly_incremental"].get(qk, 0.25)
                    os2 = sum(indexes["monthly_organic"].get(m, 1/12) for m in mos)
                    is2 = sum(indexes["monthly_incremental"].get(m, 1/12) for m in mos)
                    for mo in mos:
                        op = qo * (indexes["monthly_organic"].get(mo, 1/12) / os2) if os2 else qo / 3
                        ip = qi * (indexes["monthly_incremental"].get(mo, 1/12) / is2) if is2 else qi / 3
                        mo_label = f"{mo} {yr}" if yr else mo
                        ms_rows.append([mo_label] + [""] * (snc - 1))
                        ms_rows.extend(split_rows(vis_ranges, op, ip))
                sheets["Monthly Split"] = ms_rows

    # --- Build xlsx from raw XML with formatting ---
    def col_letter(idx):
        r = ""; i = idx
        while i >= 0: r = chr(65 + i % 26) + r; i = i // 26 - 1
        return r

    def cell_xml(ref, val, s=0):
        sa = f' s="{s}"'
        if val is None or val == "": return f'<c r="{ref}"{sa}/>'
        if isinstance(val, (int, float)): return f'<c r="{ref}"{sa} t="n"><v>{val}</v></c>'
        return f'<c r="{ref}"{sa} t="inlineStr"><is><t>{_esc(str(val))}</t></is></c>'

    # Styles: 0=normal-left, 1=header(white on dark navy, centered), 2=title(bold black, left),
    #   3=section-label(bold navy, left), 4=data-right(grid), 5=data-left(grid),
    #   6=section-label-right, 7=avg-left(bold navy, grid), 8=avg-right(bold navy, grid)
    _STYLED_STYLES = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="5">'
        '<font><sz val="10"/><color rgb="FF000000"/><name val="Calibri"/></font>'
        '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        '<font><b/><sz val="12"/><color rgb="FF000000"/><name val="Calibri"/></font>'
        '<font><b/><sz val="10"/><color rgb="FF1F3864"/><name val="Calibri"/></font>'
        '<font><b/><sz val="10"/><color rgb="FF000000"/><name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F3864"/><bgColor indexed="64"/></patternFill></fill>'
        '</fills>'
        '<borders count="3">'
        '<border><left/><right/><top/><bottom/><diagonal/></border>'
        '<border>'
          '<left style="thin"><color rgb="FFA6A6A6"/></left>'
          '<right style="thin"><color rgb="FFA6A6A6"/></right>'
          '<top style="thin"><color rgb="FFA6A6A6"/></top>'
          '<bottom style="thin"><color rgb="FFA6A6A6"/></bottom>'
          '<diagonal/>'
        '</border>'
        '<border><left/><right/><top/><bottom style="thin"><color rgb="FFA6A6A6"/></bottom><diagonal/></border>'
        '</borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="9">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="3" fillId="0" borderId="2" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="3" fillId="0" borderId="2" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="4" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="4" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )

    def sheet_xml(data_rows, sheet_title="", double_header=False):
        ncols = len(data_rows[0]) if data_rows else 1
        xml_rows = []
        merges = []
        rn = 1
        # Title row (bold black text, no background)
        if sheet_title:
            me = col_letter(max(ncols - 1, 0))
            xml_rows.append(f'<row r="{rn}" ht="24" customHeight="1">{cell_xml(f"A{rn}", sheet_title, 2)}</row>')
            merges.append(f"A{rn}:{me}{rn}")
            rn += 1
            # spacer after title
            xml_rows.append(f'<row r="{rn}" ht="6" customHeight="1"/>')
            rn += 1
        data_row_idx = 0
        for row in data_rows:
            is_header = (data_row_idx == 0) or (double_header and data_row_idx == 1)
            _non_empty = [v for v in row if v != ""]
            is_section = (not is_header and len(row) > 1 and len(_non_empty) >= 1
                          and all(v == _non_empty[0] for v in _non_empty))
            is_avg = (not is_header and row[0] == "Average")
            if is_section:
                # spacer before section
                if data_row_idx > 1:
                    xml_rows.append(f'<row r="{rn}" ht="14" customHeight="1"/>')
                    rn += 1
                # section label: bold navy text at each non-empty position, borderless elsewhere
                cells = ""
                for ci, v in enumerate(row):
                    ref = f"{col_letter(ci)}{rn}"
                    if v != "":
                        cells += cell_xml(ref, v, 3)
                    else:
                        cells += cell_xml(ref, "", 0)
                xml_rows.append(f'<row r="{rn}" ht="18" customHeight="1">{cells}</row>')
                rn += 1
                data_row_idx += 1
                continue
            if is_header:
                # dark navy header row with white bold text; empty spacer cols get no style
                cells = "".join(
                    cell_xml(f"{col_letter(ci)}{rn}", v, 0 if v == "" and ci > 0 else 1)
                    for ci, v in enumerate(row))
                xml_rows.append(f'<row r="{rn}" ht="20" customHeight="1">{cells}</row>')
                rn += 1
                data_row_idx += 1
                continue
            # data or average row — white bg, grid borders; empty spacer cols get no border
            cells = []
            for ci, v in enumerate(row):
                ref = f"{col_letter(ci)}{rn}"
                if v == "" and ci > 0:
                    cells.append(cell_xml(ref, "", 0))   # borderless spacer
                elif is_avg:
                    cells.append(cell_xml(ref, v, 7 if ci == 0 else 8))
                elif ci == 0:
                    cells.append(cell_xml(ref, v, 5))    # left-aligned
                else:
                    cells.append(cell_xml(ref, v, 4))    # right-aligned
            xml_rows.append(f'<row r="{rn}" ht="16" customHeight="1">{"".join(cells)}</row>')
            rn += 1
            data_row_idx += 1
        cw = f'<col min="1" max="1" width="24" customWidth="1"/>'
        if ncols > 1:
            cw += f'<col min="2" max="{ncols}" width="16" customWidth="1"/>'
        merge_xml = ""
        if merges:
            mc = "".join(f'<mergeCell ref="{ref}"/>' for ref in merges)
            merge_xml = f'<mergeCells count="{len(merges)}">{mc}</mergeCells>'
        return (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetViews><sheetView showGridLines="0" workbookViewId="0"/></sheetViews>'
            f'<cols>{cw}</cols>'
            f'<sheetData>{"".join(xml_rows)}</sheetData>'
            f'{merge_xml}</worksheet>'
        )

    buf = _io.BytesIO()
    snames = list(sheets.keys())
    _sheet_titles = {
        "Historical KPIs": f"ForecastPro AI — Historical KPIs  |  {account}",
        "Quarterly Forecast": f"ForecastPro AI — Quarterly Forecast  |  {account}",
        "Annual Forecast": f"ForecastPro AI — Annual Forecast  |  {account}",
    }
    _dbl_hdr_sheets = {"Quarterly Split", "Monthly Split"}
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as z:
        ov = "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(snames)+1))
        z.writestr("[Content_Types].xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{ov}</Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        ws = "".join(f'<sheet name="{_esc(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(snames, 1))
        z.writestr("xl/workbook.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{ws}</sheets></workbook>')
        rl = "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(snames)+1))
        z.writestr("xl/_rels/workbook.xml.rels", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rl}<Relationship Id="rIdS" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", _STYLED_STYLES)
        for i, n in enumerate(snames, 1):
            t = _sheet_titles.get(n, f"ForecastPro AI — {n}  |  {account}")
            dbl = (n in _dbl_hdr_sheets) and bool(improvements)
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(sheets[n], sheet_title=t, double_header=dbl))

    _safe = re.sub(r"[^a-z0-9]+", "-", account.lower()).strip("-") or "forecast"
    st.download_button("Download Excel Workbook", buf.getvalue(), f"{_safe}-forecast.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary", key=f"dl_excel_{key_suffix}")


def tab_nav_buttons(tab_names: list[str], current_index: int) -> None:
    """Render Previous / Next navigation buttons at the bottom of a tab."""
    st.markdown("---")
    cols = st.columns([1, 8, 1])
    if current_index > 0:
        with cols[0]:
            if st.button(
                f"⬅ Previous: {tab_names[current_index - 1]}",
                key=f"prev_{current_index}",
                use_container_width=True,
            ):
                st.session_state.active_tab = current_index - 1
                st.session_state.scroll_to_top = True
                st.rerun()
    if current_index < len(tab_names) - 1:
        with cols[2]:
            if st.button(
                f"Next: {tab_names[current_index + 1]} ➡",
                key=f"next_{current_index}",
                use_container_width=True,
            ):
                st.session_state.active_tab = current_index + 1
                st.session_state.scroll_to_top = True
                st.rerun()


initialize_state()
if st.session_state.pop("scroll_to_top", False):
    scroll_page_to_top()

# --- Get session (simple — no caching, no health checks) ---
session = get_session()


def load_historical_slice() -> None:
    """Populate existing preview state from the four authoritative dimensions."""
    using_data_quarter = st.session_state.get("selected_planning_quarter")
    if using_data_quarter:
        st.caption(
            f"Performing projection for {projection_quarter_choice} using {using_data_quarter} universe and max reach."
        )

    table_name = REFERENCE_HISTORICAL_TABLE
    filters = {
        "account_name": st.session_state.source_account,
        "sub_account": st.session_state.get("selected_sub_account"),
        "event": st.session_state.get("selected_event"),
        "channel": st.session_state.get("selected_channel"),
    }
    window = resolve_attribution_window(session, **filters)
    st.session_state.attribution_window = window
    rows = historical_preview(session, table_name, window, **filters)
    monthly_rows = historical_monthly_preview(session, table_name, window, **filters)

    # Sort rows in reverse chronological order (most recent quarter first)
    def _quarter_sort_key(row):
        q = row.get("campaign_quarter", "")
        parts = q.split()
        if len(parts) == 2:
            return (-int(parts[1]), -int(parts[0].replace("Q", "")))
        return (0, 0)

    rows.sort(key=_quarter_sort_key)
    default_keys = {
        f"{row['campaign_quarter']}-{row['source_week_order']}"
        for row in [
            item for item in rows
            if item["is_complete"]
        ][:4]
    }
    for row in rows:
        row["Use"] = (
            f"{row['campaign_quarter']}-{row['source_week_order']}" in default_keys
        )
    st.session_state.preview = rows
    st.session_state.monthly_history = monthly_rows
    st.session_state.confirmed = False
    st.session_state.forecast = None
    st.session_state.selected_source = table_name
    st.session_state.historical_scope_label = "Historical slice"

# --- Common header ---
brand_col, title_col, reset_col = st.columns(
    [2.2, 4.6, 1.5],
    vertical_alignment="center",
)
with brand_col:
    st.markdown(
        '<p style="color:#777;font-size:0.7rem;font-weight:700;letter-spacing:0.12em;'
        'text-transform:uppercase;margin:0;">FORECASTPRO AI</p>',
        unsafe_allow_html=True,
    )
with title_col:
    st.markdown(
        '<h1 style="font-family:Georgia,serif !important;font-weight:700 !important;'
        'font-size:2.2rem !important;line-height:1.1;text-align:center;margin:0;">Forecast Engine</h1>',
        unsafe_allow_html=True,
    )
mailops_col, reset_col = st.columns([1, 1])
with mailops_col:
    if st.button("Change MailOps Data", key="_mailops_btn", help="Add MailOps data through this tool"):
        st.session_state.mailops_mode = True
        st.rerun()
with reset_col:
    if st.button("Start New Account", key="_reset_btn", help="Clear all state and start fresh for next account"):
        reset_for_new_account()
        st.rerun()

# =============================================================================
# MAILOPS EDITOR — full-page mode, hides the forecast UI
# =============================================================================
if st.session_state.get("mailops_mode"):
    render_mailops_editor(session)
    st.stop()

st.info(st.session_state.message)

# =============================================================================
# BUILD TAB LIST — tabs appear progressively as user advances
# =============================================================================
tab_names = ["1 Inputs"]
if st.session_state.confirmed:
    tab_names.append("2 Review & Inputs")
if st.session_state.forecast:
    _is_quarterly = st.session_state.get("projection_mode", "Quarterly") == "Quarterly"
    if _is_quarterly:
        tab_names.append("3a Quarterly Forecast")
        tab_names.append("3b Monthly Split")
    else:
        tab_names.append("3a Annual Forecast")
        tab_names.append("3b Quarterly Split")
        tab_names.append("3c Monthly Split")
    tab_names.append("4 Charts")
    tab_names.append("5 Projection Calculations (QA)")

_charts_tab_idx = len(tab_names) - 2
_qa_tab_idx = len(tab_names) - 1

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
            st.session_state.scroll_to_top = True
            st.rerun()

st.markdown('<div class="compact-workflow-divider"></div>', unsafe_allow_html=True)
active_tab = st.session_state.active_tab


def compact_field_label(title: str, instruction: str, tooltip: str) -> None:
    """Keep input labels, guidance, and hover help consistent and compact."""
    st.markdown(
        f'<div style="margin:0 0 0.25rem;"><span style="font-weight:700;">{title} <span class="info-icon" title="{tooltip}" aria-label="More information">i</span></span><br><span style="color:#6b7280;font-size:0.82rem;">{instruction}</span></div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# TAB 1: INPUTS & DISCOVERY
# =============================================================================
if active_tab == 0:
    st.header("1. Select Campaign")
    st.caption("Select a campaign from the dropdown.")
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
    saved_account = st.session_state.get("source_account")
    # Returning from review/forecast must show the exact historical slice that
    # was confirmed, even if a dependent widget previously fell back to its
    # first option. A user edit invokes its callback and clears `confirmed`,
    # so this never overwrites a new in-progress selection.
    if (
        (st.session_state.get("confirmed") or st.session_state.get("forecast"))
        and saved_account
    ):
        st.session_state._widget_all_account = saved_account
        st.session_state._widget_sub_account = st.session_state.get(
            "selected_sub_account"
        )
        st.session_state._widget_event = st.session_state.get("selected_event")
        st.session_state._widget_channel = st.session_state.get("selected_channel")
    if (
        "_widget_all_account" not in st.session_state
        and saved_account in all_account_options
    ):
        st.session_state._widget_all_account = saved_account

    if st.session_state.get("_widget_all_account") not in all_account_options:
        st.session_state.pop("_widget_all_account", None)

    def _account_changed():
        account = st.session_state.get("_widget_all_account")
        st.session_state.source_account = account or None
        st.session_state.selected_sub_account = None
        st.session_state.selected_event = None
        st.session_state.selected_channel = None
        for key in ("_widget_sub_account", "_widget_event", "_widget_channel"):
            st.session_state.pop(key, None)
        clear_downstream_input_state()

        # Make account selection a useful one-click starting point.  Each
        # dependent control receives the first valid value from the account's
        # filtered hierarchy; analysts can still select another valid option.
        if not st.session_state.source_account:
            return
        try:
            account_rows = account_dimensions(session, st.session_state.source_account)
            sub_accounts = sorted({
                str(row.get("SUB_ACCOUNT")).strip()
                for row in account_rows if row.get("SUB_ACCOUNT")
            })
            if not sub_accounts:
                return
            sub_account = sub_accounts[0]
            st.session_state._widget_sub_account = sub_account
            st.session_state.selected_sub_account = sub_account

            event_rows = account_dimensions(
                session, st.session_state.source_account, sub_account=sub_account
            )
            events = sorted({
                str(row.get("EVENT")).strip()
                for row in event_rows if row.get("EVENT")
            })
            if not events:
                return
            event = events[0]
            st.session_state._widget_event = event
            st.session_state.selected_event = event

            channel_rows = account_dimensions(
                session,
                st.session_state.source_account,
                sub_account=sub_account,
                event=event,
            )
            channels = sorted({
                str(row.get("CHANNEL")).strip()
                for row in channel_rows if row.get("CHANNEL")
            })
            if channels:
                st.session_state._widget_channel = channels[0]
                st.session_state.selected_channel = channels[0]
        except Exception:
            # The normal render path will show any available dependent options.
            pass

    def _sub_account_changed():
        st.session_state.selected_sub_account = st.session_state.get("_widget_sub_account")
        st.session_state.selected_event = None
        st.session_state.selected_channel = None
        for key in ("_widget_event", "_widget_channel"):
            st.session_state.pop(key, None)
        clear_downstream_input_state()

    def _event_changed():
        st.session_state.selected_event = st.session_state.get("_widget_event")
        st.session_state.selected_channel = None
        st.session_state.pop("_widget_channel", None)
        clear_downstream_input_state()

    def _channel_changed():
        st.session_state.selected_channel = st.session_state.get("_widget_channel")
        clear_downstream_input_state()

    primary_row = st.columns(2)
    secondary_row = st.columns(2)
    with primary_row[0]:
        compact_field_label(
            "Client Name",
            "Select the relevant client before continuing.",
            "Client values align with the reporting parameters in the Multi-Tenant Results data used for Insights Studio dashboards.",
        )
        all_account_choice = st.selectbox(
            "Client Name",
            all_account_options,
            index=None,
            placeholder="– select an account",
            key="_widget_all_account",
            on_change=_account_changed,
            label_visibility="collapsed",
        )

    base_dimensions = []
    if all_account_choice:
        try:
            base_dimensions = account_dimensions(session, all_account_choice)
        except Exception as exc:
            st.warning(f"Account filters could not be loaded yet: {exc}")
    sub_options = sorted({
        str(row.get("SUB_ACCOUNT")).strip() for row in base_dimensions
        if row.get("SUB_ACCOUNT")
    })
    if (
        st.session_state.get("_widget_sub_account")
        and st.session_state.get("_widget_sub_account") not in sub_options
    ):
        st.session_state.pop("_widget_sub_account", None)

    saved_sub_account = st.session_state.get("selected_sub_account")
    if (
        "_widget_sub_account" not in st.session_state
        and saved_sub_account in sub_options
    ):
        st.session_state._widget_sub_account = saved_sub_account
    with secondary_row[0]:
        compact_field_label(
            "Campaign Name",
            "Select the campaign you would like to project.",
            "Identifies campaigns that were measured and reported as standalone campaigns.",
        )
        sub_account_choice = st.selectbox(
            "Campaign Name",
            sub_options or [""],
            index=None if sub_options else 0,
            placeholder=" ",
            key="_widget_sub_account",
            on_change=_sub_account_changed,
            label_visibility="collapsed",
            disabled=not sub_options,
            format_func=lambda value: value or "",
        )

    event_dimensions = []
    if all_account_choice and sub_account_choice:
        event_dimensions = account_dimensions(
            session, all_account_choice, sub_account=sub_account_choice
        )
    event_options = sorted({
        str(row.get("EVENT")).strip() for row in event_dimensions
        if row.get("EVENT")
    })
    if (
        st.session_state.get("_widget_event")
        and st.session_state.get("_widget_event") not in event_options
    ):
        st.session_state.pop("_widget_event", None)
    saved_event = st.session_state.get("selected_event")
    if "_widget_event" not in st.session_state and saved_event in event_options:
        st.session_state._widget_event = saved_event
    with primary_row[1]:
        compact_field_label(
            "Conversion Event",
            "Select the conversion event you would like to project.",
            "The projection uses historical performance for the selected conversion event and adjusts the projection accordingly.",
        )
        event_choice = st.selectbox(
            "Conversion Event", event_options or [""], index=None if event_options else 0, placeholder=" ",
            key="_widget_event", on_change=_event_changed, label_visibility="collapsed",
            disabled=not event_options, format_func=lambda value: value or "",
        )

    channel_dimensions = []
    if all_account_choice and sub_account_choice and event_choice:
        channel_dimensions = account_dimensions(
            session, all_account_choice,
            sub_account=sub_account_choice, event=event_choice,
        )
    channel_options = sorted({
        str(row.get("CHANNEL")).strip() for row in channel_dimensions
        if row.get("CHANNEL")
    })
    if (
        st.session_state.get("_widget_channel")
        and st.session_state.get("_widget_channel") not in channel_options
    ):
        st.session_state.pop("_widget_channel", None)
    saved_channel = st.session_state.get("selected_channel")
    if "_widget_channel" not in st.session_state and saved_channel in channel_options:
        st.session_state._widget_channel = saved_channel
    with secondary_row[1]:
        compact_field_label(
            "Marketing Channel",
            "Select the marketing channel you would like to project.",
            "Identifies the marketing channel used to deliver the campaign, such as email, display, or inbox advertising.",
        )
        channel_choice = st.selectbox(
            "Marketing Channel", channel_options or [""], index=None if channel_options else 0, placeholder=" ",
            key="_widget_channel", on_change=_channel_changed, label_visibility="collapsed",
            disabled=not channel_options, format_func=lambda value: value or "",
        )

    planning_inputs_ready = bool(
        all_account_choice and sub_account_choice and event_choice and channel_choice
    )
    try:
        available_planning_quarters = (
            planning_quarters(
                session,
                all_account_choice,
                sub_account_choice,
                channel_choice,
            )
            if planning_inputs_ready
            else []
        )
    except Exception:
        available_planning_quarters = []
    planning_quarter_scope = (
        all_account_choice,
        sub_account_choice,
        channel_choice,
    )
    scope_changed = (
        st.session_state.get("planning_quarter_scope") != planning_quarter_scope
    )
    if scope_changed:
        st.session_state.planning_quarter_scope = planning_quarter_scope
        st.session_state.pop("selected_planning_quarter", None)
        st.session_state.pop("applied_planning_key", None)
        st.session_state.pop("_widget_projection_quarter", None)
        st.session_state.pop("projection_quarter", None)

    if st.session_state.get("selected_planning_quarter") not in available_planning_quarters:
        st.session_state.pop("selected_planning_quarter", None)

    def _quarter_sort_value(label: str) -> int:
        match = re.fullmatch(r"Q([1-4])\s+(\d{4})", label.strip(), re.I)
        return int(match.group(2)) * 4 + int(match.group(1)) if match else 0

    def _next_quarter_label(label: str) -> str | None:
        match = re.fullmatch(r"Q([1-4])\s+(\d{4})", label.strip(), re.I)
        if not match:
            return None
        quarter, year = int(match.group(1)), int(match.group(2))
        return f"Q1 {year + 1}" if quarter == 4 else f"Q{quarter + 1} {year}"

    # The analyst selects the projection target. Its source universe is always
    # the immediately preceding approved planning quarter.
    current_date = datetime.now(timezone.utc)
    current_quarter = f"Q{((current_date.month - 1) // 3) + 1} {current_date.year}"
    projection_to_source = {
        projection: source
        for source in available_planning_quarters
        if (projection := _next_quarter_label(source))
        and _quarter_sort_value(projection) >= _quarter_sort_value(current_quarter)
    }
    _projection_quarter_options = sorted(
        projection_to_source,
        key=_quarter_sort_value,
    )

    proj_row = st.columns(2)
    quarter_selector_label = (
        "Starting Quarter"
        if st.session_state.get("_widget_projection_mode", "Quarterly") == "Annual"
        else "Projection Quarter"
    )
    if _projection_quarter_options:
        if st.session_state.get("_widget_projection_quarter") not in _projection_quarter_options:
            st.session_state._widget_projection_quarter = _projection_quarter_options[0]
        with proj_row[0]:
            projection_quarter_choice = st.selectbox(
                quarter_selector_label,
                _projection_quarter_options,
                key="_widget_projection_quarter",
                help="Choose the quarter to forecast. The preceding approved quarter is used automatically as the source universe.",
            )

        using_data_quarter = projection_to_source[projection_quarter_choice]
        if st.session_state.get("selected_planning_quarter") != using_data_quarter:
            st.session_state.selected_planning_quarter = using_data_quarter
            st.session_state.pop("applied_planning_key", None)
            st.session_state.forecast = None
            st.session_state.tier_adjustments = {}
            st.session_state.tier_overrides = {}

        st.markdown(
            f'<div style="margin:0.7rem 0 0.2rem;"><strong>Using Data From:</strong> <code>{using_data_quarter}</code></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Performing projection for {projection_quarter_choice} using {using_data_quarter} universe max reach."
        )
    else:
        projection_quarter_choice = None
        using_data_quarter = None
        st.session_state.pop("selected_planning_quarter", None)
        with proj_row[0]:
            st.caption(
                "No current or future projection quarter has an approved preceding source-data quarter."
            )

    with proj_row[1]:
        projection_mode = st.radio(
            "Projection Mode",
            options=["Quarterly", "Annual"],
            index=0,
            horizontal=True,
            key="_widget_projection_mode",
            help="Quarterly generates projections for the selected quarter. Annual scales the quarterly projection by 4× and applies seasonal indexes to provide a full-year projection by quarter.",
        )

    table_name = REFERENCE_HISTORICAL_TABLE
    if st.button("Load Historical Data", type="primary"):
        try:
            if not (all_account_choice and sub_account_choice and event_choice and channel_choice):
                raise ValueError("Select a client, campaign, conversion event, and marketing channel first.")
            reset_after_source()
            st.session_state.source_account = all_account_choice
            st.session_state.selected_sub_account = sub_account_choice or None
            st.session_state.selected_event = event_choice or None
            st.session_state.selected_channel = channel_choice or None
            st.session_state.projection_mode = projection_mode
            st.session_state.projection_quarter = projection_quarter_choice
            st.session_state.sources = [{"DERIVED_WEEKLY_TABLE": table_name}]
            load_historical_slice()
            if not st.session_state.preview:
                st.session_state.message = "No historical data matched the selected inputs."
            else:
                st.session_state.message = "Historical quarters are ready for review below."
            st.rerun()
        except Exception as exc:
            st.error(f"Historical data could not be loaded: {exc}")


# HISTORICAL QUARTER REVIEW — remains on the Inputs tab
# =============================================================================
if st.session_state.preview and active_tab == 0:
    st.markdown(
        '<h3 style="margin:0.2rem 0 0.3rem;">Historical Quarterly Performance '
        '<span title="Results come directly from Multi-Tenant Results data and should align with reported quarterly performance." '
        'class="info-icon" aria-label="More information">i</span></h3>',
        unsafe_allow_html=True,
    )
    st.caption("Review and approve the historical performance data before proceeding to the next step.")

    # Filter to quarters before the projection quarter, sorted most recent first
    def _quarter_sort_value(label: str) -> int:
        parts = label.strip().split()
        if len(parts) == 2:
            return int(parts[1]) * 4 + int(parts[0].replace("Q", ""))
        return 0

    _proj_q = st.session_state.get("projection_quarter")
    _proj_q_val = _quarter_sort_value(_proj_q) if _proj_q else 99999
    _eligible_preview = sorted(
        [row for row in st.session_state.preview
         if _quarter_sort_value(row["campaign_quarter"]) < _proj_q_val],
        key=lambda row: _quarter_sort_value(row["campaign_quarter"]),
        reverse=True,
    )
    # Default: pre-select the 4 most recent quarters
    for i, row in enumerate(_eligible_preview):
        if "Use" not in row or row["Use"] is None:
            row["Use"] = i < 4

    if not _eligible_preview:
        st.warning("No historical quarters exist before the selected projection quarter.")
        st.stop()

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
            }
            for row in _eligible_preview
        ]
    )
    edited = st.data_editor(
        display,
        hide_index=True,
        use_container_width=True,
        key=f"history_editor_{hash(str([r['campaign_quarter'] for r in _eligible_preview]))}",
        disabled=[column for column in display.columns if column != "Use"],
        column_config={
            "Use": st.column_config.CheckboxColumn(required=True),
            "Historical CPM": st.column_config.NumberColumn(format="$%.2f"),
            "Delivered": st.column_config.NumberColumn(format="localized"),
            "Prospects": st.column_config.NumberColumn(format="localized"),
            "Inc. customers": st.column_config.NumberColumn(format="%,.0f"),
            "Revenue": st.column_config.NumberColumn(format="$%,.0f"),
            "CPIx": st.column_config.NumberColumn(format="$%.2f"),
            "iROAS": st.column_config.NumberColumn(format="$%.3f"),
        },
    )
    selected_quarters = set(edited.loc[edited["Use"], "Quarter"].tolist())
    selected_history = [
        row
        for row in _eligible_preview
        if row["campaign_quarter"] in selected_quarters
    ]

    incomplete = [row for row in selected_history if not row["is_complete"]]
    partial_approved = False
    if incomplete:
        partial_approved = st.checkbox(
            "I reviewed and approve the selected partial quarter(s)."
        )

    # Keep the seasonal-index review with the historical selection, before the
    # user confirms it. Automatic values use the existing calculation; manual
    # values are an explicit analyst override.
    try:
        automatic_indexes = seasonal_indexes(
            session,
            st.session_state.selected_source,
            st.session_state.get("attribution_window", 30),
            account_name=st.session_state.source_account,
            sub_account=st.session_state.get("selected_sub_account"),
            event=st.session_state.get("selected_event"),
            channel=st.session_state.get("selected_channel"),
        )
        render_monthly_index_section(automatic_indexes)
    except Exception as exc:
        st.warning(f"Could not load monthly breakdown: {exc}")
    can_confirm = (
        bool(selected_history)
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
        st.session_state.active_tab = 1
        st.session_state.scroll_to_top = True
        st.rerun()


# =============================================================================
# TAB 2: REVIEW & INPUTS
# =============================================================================
if st.session_state.confirmed and active_tab == 1:
    selected_history = st.session_state.selected_history
    st.session_state.setdefault("show_historical_kpis", False)
    kpi_button_label = (
        "Hide historical quarterly KPIs"
        if st.session_state.show_historical_kpis
        else "Show historical quarterly KPIs"
    )
    if "show_historical_kpis" not in st.session_state:
        st.session_state.show_historical_kpis = False
    kpi_button_label = "Hide Historical KPIs" if st.session_state.show_historical_kpis else "Show Historical KPIs"
    if st.button(kpi_button_label, key="toggle_historical_kpis"):
        st.session_state.show_historical_kpis = not st.session_state.show_historical_kpis
        st.rerun()

    if st.session_state.show_historical_kpis:
        st.header("4. Historical Quarterly KPIs & Performance")
        _kpi_rows = []
        for row in selected_history:
            _kpi_rows.append({
                "Quarter": row["campaign_quarter"],
                "Delivered": f"{float(row['delivered_volume']):,.0f}",
                "Spend": f"${float(row['source_spend']):,.0f}",
                "Avg. Frequency": f"{float(row['frequency']):.1f}",
                "Prospects": f"{float(row['prospects']):,.0f}",
                "Inc. Customers": f"{float(row['incremental_customers']):,.0f}",
                "Inc. Revenue": f"${float(row['incremental_revenue']):,.0f}",
                "Avg. Inc. Rev": f"${float(row['average_incremental_revenue']):,.0f}",
                "CPIx": f"${float(row['cpix']):,.2f}",
                "iROAS": f"${float(row['iroas']):.3f}",
            })
        _n = len(selected_history)
        _kpi_rows.append({
            "Quarter": "Average",
            "Delivered": f"{sum(float(r['delivered_volume']) for r in selected_history) / _n:,.0f}",
            "Spend": f"${sum(float(r['source_spend']) for r in selected_history) / _n:,.0f}",
            "Avg. Frequency": f"{sum(float(r['frequency']) for r in selected_history) / _n:.1f}",
            "Prospects": f"{sum(float(r['prospects']) for r in selected_history) / _n:,.0f}",
            "Inc. Customers": f"{sum(float(r['incremental_customers']) for r in selected_history) / _n:,.0f}",
            "Inc. Revenue": f"${sum(float(r['incremental_revenue']) for r in selected_history) / _n:,.0f}",
            "Avg. Inc. Rev": f"${sum(float(r['average_incremental_revenue']) for r in selected_history) / _n:,.0f}",
            "CPIx": f"${sum(float(r['cpix']) for r in selected_history) / _n:,.2f}",
            "iROAS": f"${sum(float(r['iroas']) for r in selected_history) / _n:.3f}",
        })
        st.dataframe(pd.DataFrame(_kpi_rows), hide_index=True, use_container_width=True)

    historical_frequency = sum(
        float(row["frequency"]) for row in selected_history
    ) / len(selected_history)

    current_budget = st.session_state.current_budget
    cpm = st.session_state.cpm
    planned_reach = st.session_state.planned_reach
    max_reach = st.session_state.max_reach
    signal_utilization = st.session_state.signal_utilization

    minimum_viable_frequency = (
        current_budget * 1000 / (max_reach * cpm)
    )
    frequency_widget_key = "_widget_frequency_at_max"
    if frequency_widget_key not in st.session_state:
        st.session_state[frequency_widget_key] = float(
            st.session_state.frequency_at_max
        )

    def _frequency_changed():
        st.session_state.frequency_at_max = float(
            st.session_state[frequency_widget_key]
        )
        st.session_state.tier_adjustments = {}
        st.session_state.forecast = None
        st.session_state.message = (
            "Frequency changed. Create a new forecast draft to update results."
        )

    # Planning values are loaded from the approved Snowflake table above. The
    # field labels below are sufficient context, so avoid a repeated section heading.
    frequency_col, range_col = st.columns(2)
    planning_quarter = st.session_state.get("selected_planning_quarter")
    if planning_quarter:
        try:
            planning_key = (
                planning_quarter,
                st.session_state.source_account,
                st.session_state.selected_sub_account,
                st.session_state.selected_channel,
            )
            if (
                st.session_state.get("applied_planning_key") != planning_key
                or st.session_state.signal_utilization > 1
            ):
                values = planning_input(
                    session,
                    planning_quarter,
                    st.session_state.source_account,
                    st.session_state.selected_sub_account or "",
                    st.session_state.selected_channel or "",
                )
                st.session_state.current_budget = float(values["campaign_budget"])
                st.session_state.cpm = float(values["cpm"])
                st.session_state.planned_reach = float(values["planned_reach"])
                st.session_state.max_reach = float(values["maximum_reach"])
                planning_utilization = float(values["signal_utilization"])
                st.session_state.signal_utilization = (
                    planning_utilization / 100
                    if planning_utilization > 1
                    else planning_utilization
                )
                planning_frequency = float(values["frequency_at_max"])
                st.session_state.frequency_at_max = planning_frequency
                st.session_state[frequency_widget_key] = planning_frequency
                st.session_state.tier_overrides = {}
                st.session_state.tier_adjustments = {}
                st.session_state.applied_planning_key = planning_key
                st.session_state.message = (
                    f"{planning_quarter} planning inputs applied from Snowflake."
                )
                st.rerun()
        except ValueError:
            # There is no matched planning row for every historical slice.
            # Keep the existing/manual planning values without an on-page warning.
            pass
        except Exception:
            pass

    with frequency_col:
        frequency_at_max = st.number_input(
            "Frequency at Max Reach Utilization",
            min_value=minimum_viable_frequency,
            step=0.5,
            key=frequency_widget_key,
            on_change=_frequency_changed,
            help=(
                f"Minimum {minimum_viable_frequency:.2f} keeps Sustainable Scale "
                "at or above Current Budget."
            ),
        )
        st.session_state.frequency_at_max = float(frequency_at_max)
        st.caption(f"Historic Prospect Frequency = {historical_frequency:.1f}x")

    with range_col:
        range_percent = st.number_input(
            "One-quarter range adjustment",
            min_value=0,
            max_value=99,
            value=10,
            key="range_percent_input",
        )


    # Calculated values retained for the existing tier and forecast methodology.
    max_investment = max_reach * frequency_at_max * cpm / 1000
    maximum_scale = (max_reach * 1.25) * frequency_at_max / 1000 * cpm

    def kpi_card(col, label, value, hint="", tooltip="", accent=False):
        val_class = "kpi-value-accent" if accent else "kpi-value"
        info_html = (
            f' <span class="info-icon" title="{tooltip}" aria-label="More information">i</span>'
            if tooltip else ""
        )
        hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
        col.markdown(
            f'<div class="kpi-card"><div class="kpi-label">{label}{info_html}</div>'
            f'<div class="{val_class}">{value}</div>{hint_html}</div>',
            unsafe_allow_html=True,
        )

    # Eight evenly sized cards: four columns on desktop, with Streamlit's
    # built-in responsive stacking on smaller screens.
    row1 = st.columns(4)
    kpi_card(
        row1[0], "Current Quarterly Investment", money(current_budget),
        "Based on the most recent media plan.",
        "The investment is based on the most recent available media planning documentation.",
    )
    kpi_card(
        row1[1], "Current Quarter CPM", f"${float(cpm):,.2f}",
        "Based on the most recent media plan.",
        "The CPM is based on the most recent available media planning documentation.",
    )
    kpi_card(
        row1[2], "Current Quarter Planned Reach", number(planned_reach),
        "Expected prospects reached this quarter.",
        "The number of prospects expected to receive media at the current investment level and CPM.",
    )
    kpi_card(
        row1[3], "Current Quarter Signal Utilization", f"{signal_utilization * 100:.0f}%",
        "Share of intent-signal prospects used.",
        "The percentage of intent-signal prospects expected to be used by campaign end. For example, 75% utilization of 5M prospects uses 3.75M prospects and leaves about 25% opportunity to scale.",
    )

    row2 = st.columns(4)
    kpi_card(
        row2[0], "Max Reach to Maintain Performance", number(max_reach),
        "Reach available before 100% utilization.",
        "Prospects that can be reached before 100% signal utilization while expecting similar historical performance. This does not mean every prospect has an intent signal.",
    )
    max_volume_max_signal = max_reach * frequency_at_max
    kpi_card(
        row2[1], "Max Media Impressions at 100%", number(max_volume_max_signal),
        "Expected volume at selected frequency.",
        "Expected media volume at the selected frequency and 100% signal utilization while maintaining consistent performance.",
        accent=True,
    )
    kpi_card(
        row2[2], "Max Investment at 100%", money(max_investment),
        "Investment required at maximum volume.",
        "Maximum investment required to deliver the maximum media volume and achieve 100% signal utilization.",
        accent=True,
    )
    kpi_card(
        row2[3], "Max-Max Scale", money(maximum_scale),
        "25% additional reach beyond 100%.",
        "Represents 25% additional reach beyond 100% signal utilization. Scaling beyond 100% uses signals at rest, so marginal performance can decline quickly.",
        accent=True,
    )

    st.divider()

    # --- Calculated Investment Tiers ---
    st.subheader("Calculated investment tiers")
    high_utilization = float(signal_utilization) >= 0.90
    at_full_utilization = float(signal_utilization) >= 1.0
    labels = [
        "Current Investment",
        "Growth Momentum",
        "Strategic Growth",
        "Market Expansion",
        "Strategic Scale",
        "Optimal Scale",
    ]

    if at_full_utilization:
        # Keep Current Budget as the initial tier; derive Optimal Scale from
        # Max Reach × Frequency ÷ 1,000 × CPM, matching Excel.
        labels = ["Current Investment", "Optimal Scale"]
        calculated_tier_values = [current_budget, max_investment]
        minimum_tier_gap = 0.01
    elif high_utilization:
        midpoint = (current_budget + max_investment) / 2
        labels = ["Current Investment", "Strategic Scale", "Optimal Scale"]
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
        st.session_state.get("selected_channel"),
        st.session_state.get("attribution_window"),
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

    def _reset_calculated_tiers() -> None:
        st.session_state.tier_adjustments = {}
        _clear_stale_forecast(
            "Calculated tiers reset. Create a new forecast draft to update results."
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
                "At 100% utilization, Current Budget is the Baseline. "
                "Sustainable Scale is calculated from Max Reach and frequency."
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
            edit_col, reset_col = st.columns([1, 1])
            if edit_col.button("Edit tiers manually", key="edit_tiers_manually"):
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
            reset_col.button(
                "↺ Reset",
                key="reset_calculated_tiers",
                on_click=_reset_calculated_tiers,
                disabled=not bool(st.session_state.tier_adjustments),
                help="Restore the original automatically calculated tier values.",
            )

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
                is_adjustable = (
                    not high_utilization
                    and has_tier_headroom
                    and 0 < index < len(labels) - 1
                )
                if is_adjustable:
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

                    with st.container(border=True):
                        card_col, btn_col = st.columns([6, 1], gap="small")
                        with card_col:
                            st.markdown(
                                f'<div class="tier-name">{label}</div>'
                                f'<div class="tier-amount">{money(value)}</div>',
                                unsafe_allow_html=True,
                            )
                        with btn_col:
                            st.button(
                                "+",
                                key=f"inc_{index}",
                                on_click=_change_tier,
                                kwargs={"direction": 1},
                                use_container_width=True,
                            )
                            st.button(
                                "−",
                                key=f"dec_{index}",
                                on_click=_change_tier,
                                kwargs={"direction": -1},
                                use_container_width=True,
                            )
                else:
                    with st.container(border=True):
                        st.markdown(
                            f'<div class="tier-name">{label}</div>'
                            f'<div class="tier-amount">{money(value)}</div>',
                            unsafe_allow_html=True,
                        )
    st.divider()

    # --- Improvement Scenarios ---
    if "num_scenarios" not in st.session_state:
        st.session_state.num_scenarios = 2

    def _add_scenario():
        if st.session_state.num_scenarios < 10:
            st.session_state.num_scenarios += 1
            _clear_stale_forecast(
                "Improvement scenario added. Create a new forecast draft to update results."
            )

    def _remove_scenario():
        if st.session_state.num_scenarios > 1:
            removed_index = st.session_state.num_scenarios - 1
            st.session_state.pop(f"scenario_name_{removed_index}", None)
            st.session_state.pop(f"scenario_factor_{removed_index}", None)
            st.session_state.num_scenarios -= 1
            _clear_stale_forecast(
                "Improvement scenario removed. Create a new forecast draft to update results."
            )

    num_scenarios = st.session_state.num_scenarios
    scenario_heading_col, scenario_add_col, scenario_remove_col = st.columns([6, 1.35, 1.15])
    with scenario_heading_col:
        st.markdown(
            '<h3 style="margin:0.2rem 0 0.3rem;">Forecasting Adjustment Scenarios '
            '<span title="Test the effect of one or more improvement assumptions on the forecast. '
            'Scenario factors preserve decimal precision in inputs, results, and charts." '
            'class="info-icon" aria-label="More information">i</span></h3>',
            unsafe_allow_html=True,
        )
    with scenario_add_col:
        if num_scenarios < 10:
            st.button("+ Add", key="add_scenario_heading", on_click=_add_scenario)
    with scenario_remove_col:
        st.button(
            "× Remove",
            key="remove_scenario_heading",
            on_click=_remove_scenario,
            disabled=num_scenarios <= 1,
            help="Remove the last improvement scenario.",
        )

    scenario_factors = []
    scenario_names = []

    for row_start in range(0, num_scenarios, 5):
        row_end = min(row_start + 5, num_scenarios)
        cols = st.columns(row_end - row_start)
        for idx, col in enumerate(cols):
            scenario_idx = row_start + idx
            default_factor = 15.0 if scenario_idx == 1 else 10.0
            name = col.text_input(
                f"Scenario {scenario_idx + 1} name",
                value=f"Scenario {scenario_idx + 1}",
                key=f"scenario_name_{scenario_idx}",
                label_visibility="collapsed",
            )
            factor = col.number_input(
                f"Improvement Factor (%)",
                min_value=0.0,
                max_value=99.0,
                value=15.0 if scenario_idx == 1 else 10.0,
                step=0.5,
                key=f"scenario_factor_{scenario_idx}",
            )
            scenario_names.append(name)
            scenario_factors.append(factor)

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
    seasonal_indexes_are_valid = manual_seasonal_indexes_valid()
    forecast_ready = (
        max_investment >= current_budget
        and tiers_strictly_increasing
        and calculated_tiers_available
        and seasonal_indexes_are_valid
    )
    if not forecast_ready:
        if not calculated_tiers_available:
            st.error(
                "Forecast is paused: there is no calculated headroom above Current "
                "Budget. Use the recommended frequency or enter strictly increasing "
                "manual tiers."
            )
        elif not seasonal_indexes_are_valid:
            st.error(
                "Forecast is paused because each Manual seasonal-index table must "
                "total exactly 100%."
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
            st.session_state.message = "Forecast draft created."
            st.session_state.active_tab = 2
            st.session_state.scroll_to_top = True
            st.rerun()
        except Exception as exc:
            st.error(f"Forecast calculation failed: {exc}")

    tab_nav_buttons(tab_names, 1)


# =============================================================================
# TAB 3: FORECAST RESULTS
# =============================================================================
if st.session_state.forecast and active_tab == 2:
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

    try:
        _idx_session = get_session()
        st.session_state["_cached_indexes"] = effective_monthly_indexes(seasonal_indexes(
            _idx_session,
            st.session_state.selected_source,
            attribution_window=st.session_state.get("attribution_window", 30),
            account_name=st.session_state.get("source_account"),
            sub_account=st.session_state.get("selected_sub_account"),
            event=st.session_state.get("selected_event"),
            channel=st.session_state.get("selected_channel"),
        ))
    except Exception:
        pass

    st.header("Forecast Output Ranges")
    _is_quarterly_mode = st.session_state.get("projection_mode", "Quarterly") == "Quarterly"

    if not _is_quarterly_mode:
        _scenario_options = ["Baseline"]
        for _sn, _sf, _sr in result["improvements"]:
            _scenario_options.append(f"+{float(_sf)*100:.0f}% Improvement")
        st.session_state.setdefault("annual_scenario", "Baseline")
        _selected_scenario = st.radio(
            "Scenario for Quarterly & Monthly Splits",
            options=_scenario_options,
            index=_scenario_options.index(st.session_state.get("annual_scenario", "Baseline"))
                if st.session_state.get("annual_scenario", "Baseline") in _scenario_options else 0,
            horizontal=True,
            key="_widget_annual_scenario",
            help="This selection applies to the Quarterly Split and Monthly Split tabs as well.",
        )
        st.session_state.annual_scenario = _selected_scenario
    _first_tier_label = visible_ranges[0].tier_label if visible_ranges else ""
    # Build marginal ranges from projections across all historical quarters
    from collections import defaultdict as _defaultdict
    _marginal_cpix_values: dict[str, list[float]] = _defaultdict(list)
    _marginal_iroas_values: dict[str, list[float]] = _defaultdict(list)
    for row in visible_projections:
        if row.marginal_cpix is not None and row.marginal_cpix > 0:
            _marginal_cpix_values[row.tier_label].append(float(row.marginal_cpix))
        if row.marginal_iroas is not None and row.marginal_iroas > 0:
            _marginal_iroas_values[row.tier_label].append(float(row.marginal_iroas))

    _sig_util_all = {
        row.tier_label: float(row.new_signal_utilization * 100)
        for row in visible_projections
        if row.historical_quarter == latest_quarter
    }
    st.session_state["_cached_sig_util"] = _sig_util_all

    if _is_quarterly_mode:
        # --- Quarterly mode: show one-quarter baseline table ---
        _proj_q_label = st.session_state.get("projection_quarter", "One Quarter")
        st.subheader(f"{_proj_q_label} Projection")
        range_frame = pd.DataFrame([
            {"Tier": row.tier_label,
             "Investment Tier": _fmt_dollar_commas(float(row.investment)),
             "Delivered Volume": f"{float(row.delivered_volume):,.0f}",
             "# of Prospects": f"{float(row.prospects):,.0f}",
             "Inc. Customers": _range_str(
                 float(row.incremental_customers.minimum),
                 float(row.incremental_customers.maximum),
                 _fmt_compact_k),
             "Incremental Revenue": _range_str(
                 float(row.incremental_revenue.minimum),
                 float(row.incremental_revenue.maximum),
                 _fmt_dollar_compact_m),
             "CPIx": _range_str(
                 float(row.cpix.minimum), float(row.cpix.maximum), _fmt_dollar_0),
             "iROAS": _range_str(
                 float(row.iroas.minimum), float(row.iroas.maximum), _fmt_iroas),
             "Marginal CPIx": _range_str(
                 min(_marginal_cpix_values[row.tier_label]),
                 max(_marginal_cpix_values[row.tier_label]),
                 _fmt_dollar_0)
                 if _marginal_cpix_values.get(row.tier_label) and row.tier_label != _first_tier_label
                 else "—",
             "Marginal iROAS": _range_str(
                 min(_marginal_iroas_values[row.tier_label]),
                 max(_marginal_iroas_values[row.tier_label]),
                 _fmt_iroas)
                 if _marginal_iroas_values.get(row.tier_label) and row.tier_label != _first_tier_label
                 else "—"}
            for row in visible_ranges
        ])
        st.dataframe(range_frame, hide_index=True, use_container_width=True)

    # --- Sub-content depends on projection mode ---
    _is_quarterly_mode = st.session_state.get("projection_mode", "Quarterly") == "Quarterly"

    # === Helper: render improvement scenarios ===
    def _render_improvement_scenarios(simple_headers=False):
        _range_by_tier = {r.tier_label: r for r in visible_ranges}
        _range_adj = st.session_state.get("range_percent_input", 10) / 100
        _sig_util_by_tier = {
            row.tier_label: float(row.new_signal_utilization * 100)
            for row in visible_projections
            if row.historical_quarter == latest_quarter
        }
        for name, factor, rows in result["improvements"]:
            if simple_headers:
                st.subheader(f"+{float(factor)*100:.0f}% Improvement")
            else:
                st.markdown(f'<div class="kpi-card" style="margin-top:1rem;">'
                    f'<div class="kpi-label">{name}</div>'
                    f'<div class="kpi-value">+{float(factor)*100:.0f}% improvement</div></div>', unsafe_allow_html=True)
            from collections import defaultdict as _dd
            _imp_by_tier: dict[str, list] = _dd(list)
            for r in rows:
                if visible_tier(r.tier_label, result["show_expansion"]):
                    _imp_by_tier[r.tier_label].append(r)
            scenario_rows = []
            for tier_label, tier_rows in _imp_by_tier.items():
                rng = _range_by_tier.get(tier_label)
                custs = [float(r.incremental_customers) for r in tier_rows]
                revs = [float(r.incremental_revenue) for r in tier_rows]
                cpixs = [float(r.cpix) for r in tier_rows]
                iroass = [float(r.iroas) for r in tier_rows]
                mcpixs = [float(r.marginal_cpix) for r in tier_rows if r.marginal_cpix and r.marginal_cpix > 0]
                miroass = [float(r.marginal_iroas) for r in tier_rows if r.marginal_iroas and r.marginal_iroas > 0]
                if len(tier_rows) == 1:
                    c = custs[0]
                    cust_range = _range_str(c * (1 - _range_adj), c * (1 + _range_adj), _fmt_compact_k)
                    rv = revs[0]
                    rev_range = _range_str(rv * (1 - _range_adj), rv * (1 + _range_adj), _fmt_dollar_compact_m)
                    cx = cpixs[0]
                    cpix_range = _range_str(cx / (1 + _range_adj), cx / (1 - _range_adj), _fmt_dollar_0)
                    ir = iroass[0]
                    iroas_range = _range_str(ir * (1 - _range_adj), ir * (1 + _range_adj), _fmt_iroas)
                    if mcpixs:
                        mc = mcpixs[0]
                        mcpix_range = _range_str(mc / (1 + _range_adj), mc / (1 - _range_adj), _fmt_dollar_0)
                    else:
                        mcpix_range = "—"
                    if miroass:
                        mi = miroass[0]
                        miroas_range = _range_str(mi * (1 - _range_adj), mi * (1 + _range_adj), _fmt_iroas)
                    else:
                        miroas_range = "—"
                else:
                    cust_range = _range_str(min(custs), max(custs), _fmt_compact_k)
                    rev_range = _range_str(min(revs), max(revs), _fmt_dollar_compact_m)
                    cpix_range = _range_str(min(cpixs), max(cpixs), _fmt_dollar_0)
                    iroas_range = _range_str(min(iroass), max(iroass), _fmt_iroas)
                    mcpix_range = _range_str(min(mcpixs), max(mcpixs), _fmt_dollar_0) if mcpixs else "—"
                    miroas_range = _range_str(min(miroass), max(miroass), _fmt_iroas) if miroass else "—"
                if tier_label == _first_tier_label:
                    mcpix_range = "—"
                    miroas_range = "—"
                scenario_rows.append({
                    "Tier": tier_label,
                    "Investment Tier": _fmt_dollar_commas(float(tier_rows[0].investment)),
                    "Delivered Volume": f"{float(rng.delivered_volume):,.0f}" if rng else "—",
                    "# of Prospects": f"{float(rng.prospects):,.0f}" if rng else "—",
                    "Inc. Customers": cust_range,
                    "Incremental Revenue": rev_range,
                    "CPIx": cpix_range,
                    "iROAS": iroas_range,
                    "Marginal CPIx": mcpix_range,
                    "Marginal iROAS": miroas_range,
                    "Signal Utilization": f"{_sig_util_by_tier.get(tier_label, 0):.1f}%",
                })
            if scenario_rows:
                st.dataframe(pd.DataFrame(scenario_rows), hide_index=True, use_container_width=True)

    if _is_quarterly_mode:
        # Quarterly mode: improvement scenarios inline with simple headers
        _render_improvement_scenarios(simple_headers=True)
    else:
        # Annual mode: show annual baseline + improvements inline (x4 multiplier)
        st.subheader("Annual Projection")
        annual_frame = pd.DataFrame([
            {"Tier": row.tier_label,
             "Investment": _fmt_dollar_commas(float(row.investment) * 4),
             "Delivered": f"{float(row.delivered_volume) * 4:,.0f}",
             "Prospects": f"{float(row.prospects) * 4:,.0f}",
             "Inc. Cust": _range_str(
                 float(row.incremental_customers.minimum) * 4,
                 float(row.incremental_customers.maximum) * 4,
                 _fmt_compact_k),
             "Inc. Rev": _range_str(
                 float(row.incremental_revenue.minimum) * 4,
                 float(row.incremental_revenue.maximum) * 4,
                 _fmt_dollar_compact_m),
             "CPIx": _range_str(
                 float(row.cpix.minimum), float(row.cpix.maximum), _fmt_dollar_0),
             "iROAS": _range_str(
                 float(row.iroas.minimum), float(row.iroas.maximum), _fmt_iroas),
             "Marginal CPIx": _range_str(
                 min(_marginal_cpix_values[row.tier_label]),
                 max(_marginal_cpix_values[row.tier_label]),
                 _fmt_dollar_0)
                 if _marginal_cpix_values.get(row.tier_label) and row.tier_label != _first_tier_label
                 else "—",
             "Marginal iROAS": _range_str(
                 min(_marginal_iroas_values[row.tier_label]),
                 max(_marginal_iroas_values[row.tier_label]),
                 _fmt_iroas)
                 if _marginal_iroas_values.get(row.tier_label) and row.tier_label != _first_tier_label
                 else "—",
             "% Utilization": f"{_sig_util_all.get(row.tier_label, 0):.0f}%"}
            for row in visible_ranges
        ])
        st.dataframe(annual_frame, hide_index=True, use_container_width=True)

        # Annual improvement scenarios
        _range_adj_ann = st.session_state.get("range_percent_input", 10) / 100
        for name, factor, rows in result["improvements"]:
            st.subheader(f"+{float(factor)*100:.0f}% Improvement")
            from collections import defaultdict as _dd_ann
            _imp_by_tier_ann: dict[str, list] = _dd_ann(list)
            for r in rows:
                if visible_tier(r.tier_label, result["show_expansion"]):
                    _imp_by_tier_ann[r.tier_label].append(r)
            imp_rows = []
            for tier_label, tier_rows in _imp_by_tier_ann.items():
                rng = {r.tier_label: r for r in visible_ranges}.get(tier_label)
                custs = [float(r.incremental_customers) * 4 for r in tier_rows]
                revs = [float(r.incremental_revenue) * 4 for r in tier_rows]
                cpixs = [float(r.cpix) for r in tier_rows]
                iroass = [float(r.iroas) for r in tier_rows]
                mcpixs = [float(r.marginal_cpix) for r in tier_rows if r.marginal_cpix and r.marginal_cpix > 0]
                miroass = [float(r.marginal_iroas) for r in tier_rows if r.marginal_iroas and r.marginal_iroas > 0]
                if len(tier_rows) == 1:
                    c = custs[0]
                    cust_range = _range_str(c * (1 - _range_adj_ann), c * (1 + _range_adj_ann), _fmt_compact_k)
                    rv = revs[0]
                    rev_range = _range_str(rv * (1 - _range_adj_ann), rv * (1 + _range_adj_ann), _fmt_dollar_compact_m)
                    cx = cpixs[0]
                    cpix_range = _range_str(cx / (1 + _range_adj_ann), cx / (1 - _range_adj_ann), _fmt_dollar_0)
                    ir = iroass[0]
                    iroas_range = _range_str(ir * (1 - _range_adj_ann), ir * (1 + _range_adj_ann), _fmt_iroas)
                    mcpix_range = _range_str(mcpixs[0] / (1 + _range_adj_ann), mcpixs[0] / (1 - _range_adj_ann), _fmt_dollar_0) if mcpixs else "—"
                    miroas_range = _range_str(miroass[0] * (1 - _range_adj_ann), miroass[0] * (1 + _range_adj_ann), _fmt_iroas) if miroass else "—"
                else:
                    cust_range = _range_str(min(custs), max(custs), _fmt_compact_k)
                    rev_range = _range_str(min(revs), max(revs), _fmt_dollar_compact_m)
                    cpix_range = _range_str(min(cpixs), max(cpixs), _fmt_dollar_0)
                    iroas_range = _range_str(min(iroass), max(iroass), _fmt_iroas)
                    mcpix_range = _range_str(min(mcpixs), max(mcpixs), _fmt_dollar_0) if mcpixs else "—"
                    miroas_range = _range_str(min(miroass), max(miroass), _fmt_iroas) if miroass else "—"
                if tier_label == _first_tier_label:
                    mcpix_range = "—"
                    miroas_range = "—"
                imp_rows.append({
                    "Tier": tier_label,
                    "Investment": _fmt_dollar_commas(float(tier_rows[0].investment) * 4),
                    "Delivered": f"{float(rng.delivered_volume) * 4:,.0f}" if rng else "—",
                    "Prospects": f"{float(rng.prospects) * 4:,.0f}" if rng else "—",
                    "Inc. Cust": cust_range,
                    "Inc. Rev": rev_range,
                    "CPIx": cpix_range,
                    "iROAS": iroas_range,
                    "Marginal CPIx": mcpix_range,
                    "Marginal iROAS": miroas_range,
                    "% Utilization": f"{_sig_util_all.get(tier_label, 0):.0f}%",
                })
            if imp_rows:
                st.dataframe(pd.DataFrame(imp_rows), hide_index=True, use_container_width=True)


    _render_download_button("tab3a")

    tab_nav_buttons(tab_names, 2)


# =============================================================================
# TAB 3b: QUARTERLY SPLIT (annual mode only)
# =============================================================================
if (st.session_state.forecast
    and st.session_state.get("projection_mode", "Quarterly") != "Quarterly"
    and active_tab == 3):
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
    _first_tier_label = visible_ranges[0].tier_label if visible_ranges else ""
    from collections import defaultdict as _dd_qs
    _marginal_cpix_values: dict[str, list[float]] = _dd_qs(list)
    _marginal_iroas_values: dict[str, list[float]] = _dd_qs(list)
    for row in visible_projections:
        if row.marginal_cpix is not None and row.marginal_cpix > 0:
            _marginal_cpix_values[row.tier_label].append(float(row.marginal_cpix))
        if row.marginal_iroas is not None and row.marginal_iroas > 0:
            _marginal_iroas_values[row.tier_label].append(float(row.marginal_iroas))
    _sig_util_by_tier = {
        row.tier_label: float(row.new_signal_utilization * 100)
        for row in visible_projections
        if row.historical_quarter == latest_quarter
    }
    _range_adj = st.session_state.get("range_percent_input", 10) / 100

    st.header("Quarterly Split")
    _annual_scenario = st.session_state.get("annual_scenario", "Baseline")
    _imp_factor_val = 0.0
    for _name, _factor, _rows in result["improvements"]:
        if f"+{float(_factor)*100:.0f}% Improvement" == _annual_scenario:
            _imp_factor_val = float(_factor)
            break
    _imp_mult = 1 + _imp_factor_val
    if _annual_scenario != "Baseline":
        st.caption(f"Annual forecast ({_annual_scenario}) distributed across Q1-Q4 using seasonal indexes.")
    else:
        st.caption("The annual forecast is distributed across Q1-Q4 using seasonal indexes.")

    def _q_key_fn(ql):
        _m = re.match(r"Q(\d)", ql)
        return f"Q{_m.group(1)}" if _m else "Q1"

    try:
        session = get_session()
        indexes = effective_monthly_indexes(seasonal_indexes(
            session,
            st.session_state.selected_source,
            attribution_window=st.session_state.get("attribution_window", 30),
            account_name=st.session_state.get("source_account"),
            sub_account=st.session_state.get("selected_sub_account"),
            event=st.session_state.get("selected_event"),
            channel=st.session_state.get("selected_channel"),
        ))
        _rq_ui = rolling_quarters(st.session_state.get("projection_quarter", "Q1 2026"))
        for _rq_label in _rq_ui:
            q_key = _q_key_fn(_rq_label)
            o_pct = indexes["quarterly_organic"].get(q_key, 0.25)
            i_pct = indexes["quarterly_incremental"].get(q_key, 0.25)
            st.subheader(_rq_label)
            qtr_rows = []
            for r in visible_ranges:
                label = r.tier_label
                inv = float(r.investment) * 4 * o_pct
                delivered = float(r.delivered_volume) * 4 * o_pct
                prospects = float(r.prospects) * 4 * o_pct
                cust_min = float(r.incremental_customers.minimum) * 4 * i_pct * _imp_mult
                cust_max = float(r.incremental_customers.maximum) * 4 * i_pct * _imp_mult
                rev_min = float(r.incremental_revenue.minimum) * 4 * i_pct * _imp_mult
                rev_max = float(r.incremental_revenue.maximum) * 4 * i_pct * _imp_mult
                cpix_min = inv / cust_max if cust_max > 0 else 0
                cpix_max = inv / cust_min if cust_min > 0 else 0
                iroas_min = rev_min / inv if inv > 0 else 0
                iroas_max = rev_max / inv if inv > 0 else 0
                qtr_rows.append({
                    "Tiers": label,
                    "Investment": _fmt_dollar_commas(inv),
                    "Delivered": f"{delivered:,.0f}",
                    "Prospects": f"{prospects:,.0f}",
                    "Inc. Cust": _range_str(cust_min, cust_max, _fmt_compact_k),
                    "Inc. Rev": _range_str(rev_min, rev_max, _fmt_dollar_compact_m),
                    "CPIx": _range_str(cpix_min, cpix_max, _fmt_dollar_0),
                    "iROAS": _range_str(iroas_min, iroas_max, _fmt_iroas),
                    "% Utilization": f"{_sig_util_by_tier.get(label, 0):.0f}%",
                })
            st.dataframe(pd.DataFrame(qtr_rows), hide_index=True, use_container_width=True)
    except Exception as exc:
        st.warning(f"Could not compute quarterly split: {exc}")

    _render_download_button("tab3b_qs")
    tab_nav_buttons(tab_names, 3)


# =============================================================================
# TAB 3c: MONTHLY SPLIT (annual mode only)
# =============================================================================
if (st.session_state.forecast
    and st.session_state.get("projection_mode", "Quarterly") != "Quarterly"
    and active_tab == 4):
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
    _first_tier_label = visible_ranges[0].tier_label if visible_ranges else ""
    from collections import defaultdict as _dd_ms2
    _marginal_cpix_values: dict[str, list[float]] = _dd_ms2(list)
    _marginal_iroas_values: dict[str, list[float]] = _dd_ms2(list)
    for row in visible_projections:
        if row.marginal_cpix is not None and row.marginal_cpix > 0:
            _marginal_cpix_values[row.tier_label].append(float(row.marginal_cpix))
        if row.marginal_iroas is not None and row.marginal_iroas > 0:
            _marginal_iroas_values[row.tier_label].append(float(row.marginal_iroas))
    _sig_util_by_tier = {
        row.tier_label: float(row.new_signal_utilization * 100)
        for row in visible_projections
        if row.historical_quarter == latest_quarter
    }
    _range_adj = st.session_state.get("range_percent_input", 10) / 100

    QUARTER_MONTHS_MAP = {
        1: ["Jan", "Feb", "Mar"],
        2: ["Apr", "May", "Jun"],
        3: ["Jul", "Aug", "Sep"],
        4: ["Oct", "Nov", "Dec"],
    }

    st.header("Monthly Split")
    _annual_scenario = st.session_state.get("annual_scenario", "Baseline")
    _imp_factor_val = 0.0
    for _name, _factor, _rows in result["improvements"]:
        if f"+{float(_factor)*100:.0f}% Improvement" == _annual_scenario:
            _imp_factor_val = float(_factor)
            break
    _imp_mult = 1 + _imp_factor_val
    if _annual_scenario != "Baseline":
        st.caption(f"Annual forecast ({_annual_scenario}) distributed across all 12 months using seasonal indexes.")
    else:
        st.caption("Annual forecast distributed across all 12 months using seasonal indexes.")

    _am_view_mode = st.radio("Group by", ("Month", "Tier"), horizontal=True, key="_am_view_mode")

    def _q_key_fn(ql):
        _m = re.match(r"Q(\d)", ql)
        return f"Q{_m.group(1)}" if _m else "Q1"

    try:
        session = get_session()
        indexes = effective_monthly_indexes(seasonal_indexes(
            session,
            st.session_state.selected_source,
            attribution_window=st.session_state.get("attribution_window", 30),
            account_name=st.session_state.get("source_account"),
            sub_account=st.session_state.get("selected_sub_account"),
            event=st.session_state.get("selected_event"),
            channel=st.session_state.get("selected_channel"),
        ))

        if _am_view_mode == "Tier":
            for r in visible_ranges:
                label = r.tier_label
                st.subheader(f"{label} ({_fmt_dollar_commas(float(r.investment) * 4)})")
                tier_month_rows = []
                _rq_ms = rolling_quarters(st.session_state.get("projection_quarter", "Q1 2026"))
                for _ql in _rq_ms:
                    _qk = _q_key_fn(_ql)
                    _qyr = re.search(r"\d{4}", _ql)
                    _yr = _qyr.group() if _qyr else ""
                    q_num = int(_qk[1])
                    months = QUARTER_MONTHS_MAP[q_num]
                    org_sum = sum(indexes["monthly_organic"].get(m, 1/12) for m in months)
                    inc_sum = sum(indexes["monthly_incremental"].get(m, 1/12) for m in months)
                    q_org = indexes["quarterly_organic"].get(_qk, 0.25)
                    q_inc = indexes["quarterly_incremental"].get(_qk, 0.25)
                    for month in months:
                        org_pct = q_org * (indexes["monthly_organic"].get(month, 1/12) / org_sum) if org_sum else q_org / 3
                        inc_pct = q_inc * (indexes["monthly_incremental"].get(month, 1/12) / inc_sum) if inc_sum else q_inc / 3
                        inv = float(r.investment) * 4 * org_pct
                        delivered = float(r.delivered_volume) * 4 * org_pct
                        prospects = float(r.prospects) * 4 * org_pct
                        cust_min = float(r.incremental_customers.minimum) * 4 * inc_pct * _imp_mult
                        cust_max = float(r.incremental_customers.maximum) * 4 * inc_pct * _imp_mult
                        rev_min = float(r.incremental_revenue.minimum) * 4 * inc_pct * _imp_mult
                        rev_max = float(r.incremental_revenue.maximum) * 4 * inc_pct * _imp_mult
                        cpix_min = inv / cust_max if cust_max > 0 else 0
                        cpix_max = inv / cust_min if cust_min > 0 else 0
                        iroas_min = rev_min / inv if inv > 0 else 0
                        iroas_max = rev_max / inv if inv > 0 else 0
                        tier_month_rows.append({
                            "Month": f"{month} {_yr}",
                            "Investment": _fmt_dollar_commas(inv),
                            "Delivered": f"{delivered:,.0f}",
                            "Prospects": f"{prospects:,.0f}",
                            "Inc. Cust": _range_str(cust_min, cust_max, _fmt_compact_k),
                            "Inc. Rev": _range_str(rev_min, rev_max, _fmt_dollar_compact_m),
                            "CPIx": _range_str(cpix_min, cpix_max, _fmt_dollar_0),
                            "iROAS": _range_str(iroas_min, iroas_max, _fmt_iroas),
                            "% Utilization": f"{_sig_util_by_tier.get(label, 0):.0f}%",
                        })
                st.dataframe(pd.DataFrame(tier_month_rows), hide_index=True, use_container_width=True)
        else:
            _rq_ms2 = rolling_quarters(st.session_state.get("projection_quarter", "Q1 2026"))
            for _ql2 in _rq_ms2:
                _qk2 = _q_key_fn(_ql2)
                _qyr2 = re.search(r"\d{4}", _ql2)
                _yr2 = _qyr2.group() if _qyr2 else ""
                q_num = int(_qk2[1])
                months = QUARTER_MONTHS_MAP[q_num]
                org_sum = sum(indexes["monthly_organic"].get(m, 1/12) for m in months)
                inc_sum = sum(indexes["monthly_incremental"].get(m, 1/12) for m in months)
                q_org = indexes["quarterly_organic"].get(_qk2, 0.25)
                q_inc = indexes["quarterly_incremental"].get(_qk2, 0.25)

                for month in months:
                    org_pct = q_org * (indexes["monthly_organic"].get(month, 1/12) / org_sum) if org_sum else q_org / 3
                    inc_pct = q_inc * (indexes["monthly_incremental"].get(month, 1/12) / inc_sum) if inc_sum else q_inc / 3

                    st.subheader(f"{month} {_yr2}")
                    month_rows = []
                    for r in visible_ranges:
                        label = r.tier_label
                        inv = float(r.investment) * 4 * org_pct
                        delivered = float(r.delivered_volume) * 4 * org_pct
                        prospects = float(r.prospects) * 4 * org_pct
                        cust_min = float(r.incremental_customers.minimum) * 4 * inc_pct * _imp_mult
                        cust_max = float(r.incremental_customers.maximum) * 4 * inc_pct * _imp_mult
                        rev_min = float(r.incremental_revenue.minimum) * 4 * inc_pct * _imp_mult
                        rev_max = float(r.incremental_revenue.maximum) * 4 * inc_pct * _imp_mult
                        cpix_min = inv / cust_max if cust_max > 0 else 0
                        cpix_max = inv / cust_min if cust_min > 0 else 0
                        iroas_min = rev_min / inv if inv > 0 else 0
                        iroas_max = rev_max / inv if inv > 0 else 0
                        month_rows.append({
                            "Tiers": label,
                            "Investment": _fmt_dollar_commas(inv),
                            "Delivered": f"{delivered:,.0f}",
                            "Prospects": f"{prospects:,.0f}",
                            "Inc. Cust": _range_str(cust_min, cust_max, _fmt_compact_k),
                            "Inc. Rev": _range_str(rev_min, rev_max, _fmt_dollar_compact_m),
                            "CPIx": _range_str(cpix_min, cpix_max, _fmt_dollar_0),
                            "iROAS": _range_str(iroas_min, iroas_max, _fmt_iroas),
                            "% Utilization": f"{_sig_util_by_tier.get(label, 0):.0f}%",
                        })
                    st.dataframe(pd.DataFrame(month_rows), hide_index=True, use_container_width=True)

    except Exception as exc:
        st.warning(f"Could not compute monthly split: {exc}")

    _render_download_button("tab3c_ms")
    tab_nav_buttons(tab_names, 4)


# =============================================================================
# TAB 3b: QUARTERLY MONTHLY SPLIT (only in quarterly mode)
# =============================================================================
if (st.session_state.forecast
    and st.session_state.get("projection_mode", "Quarterly") == "Quarterly"
    and active_tab == 3):
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
    _first_tier_label = visible_ranges[0].tier_label if visible_ranges else ""

    # Marginal values
    from collections import defaultdict as _dd_ms
    _marginal_cpix_values: dict[str, list[float]] = _dd_ms(list)
    _marginal_iroas_values: dict[str, list[float]] = _dd_ms(list)
    for row in visible_projections:
        if row.marginal_cpix is not None and row.marginal_cpix > 0:
            _marginal_cpix_values[row.tier_label].append(float(row.marginal_cpix))
        if row.marginal_iroas is not None and row.marginal_iroas > 0:
            _marginal_iroas_values[row.tier_label].append(float(row.marginal_iroas))

    # Signal utilization
    _sig_util_by_tier = {
        row.tier_label: float(row.new_signal_utilization * 100)
        for row in visible_projections
        if row.historical_quarter == latest_quarter
    }

    # Determine projection quarter months
    _proj_q = st.session_state.get("projection_quarter", "")
    import re as _re_ms
    _pq_match = _re_ms.match(r"Q(\d)\s+(\d{4})", _proj_q)
    if _pq_match:
        _pq_num = int(_pq_match.group(1))
    else:
        _pq_num = 1
    QUARTER_MONTHS_MAP = {
        1: ["Jan", "Feb", "Mar"],
        2: ["Apr", "May", "Jun"],
        3: ["Jul", "Aug", "Sep"],
        4: ["Oct", "Nov", "Dec"],
    }
    _proj_months = QUARTER_MONTHS_MAP[_pq_num]

    st.header(f"Quarterly Monthly Split: {_proj_q}")
    st.caption("Quarterly forecast distributed across the 3 months using seasonal indexes.")

    _qm_view_mode = st.radio("Group by", ("Month", "Tier"), horizontal=True, key="_qm_view_mode")

    try:
        session = get_session()
        indexes = effective_monthly_indexes(seasonal_indexes(
            session,
            st.session_state.selected_source,
            attribution_window=st.session_state.get("attribution_window", 30),
            account_name=st.session_state.get("source_account"),
            sub_account=st.session_state.get("selected_sub_account"),
            event=st.session_state.get("selected_event"),
            channel=st.session_state.get("selected_channel"),
        ))

        # Compute monthly proportions within this quarter
        org_sum = sum(indexes["monthly_organic"].get(m, 1/12) for m in _proj_months)
        inc_sum = sum(indexes["monthly_incremental"].get(m, 1/12) for m in _proj_months)

        _range_adj = st.session_state.get("range_percent_input", 10) / 100

        if _qm_view_mode == "Tier":
            for r in visible_ranges:
                label = r.tier_label
                st.subheader(f"{label} ({_fmt_dollar_commas(float(r.investment))})")
                tier_month_rows = []
                for month in _proj_months:
                    m_org_pct = indexes["monthly_organic"].get(month, 1/12) / org_sum if org_sum else 1/3
                    m_inc_pct = indexes["monthly_incremental"].get(month, 1/12) / inc_sum if inc_sum else 1/3
                    inv = float(r.investment) * m_org_pct
                    delivered = float(r.delivered_volume) * m_org_pct
                    prospects = float(r.prospects) * m_org_pct
                    cust_min = float(r.incremental_customers.minimum) * m_inc_pct
                    cust_max = float(r.incremental_customers.maximum) * m_inc_pct
                    rev_min = float(r.incremental_revenue.minimum) * m_inc_pct
                    rev_max = float(r.incremental_revenue.maximum) * m_inc_pct
                    cpix_min = inv / cust_max if cust_max > 0 else 0
                    cpix_max = inv / cust_min if cust_min > 0 else 0
                    iroas_min = rev_min / inv if inv > 0 else 0
                    iroas_max = rev_max / inv if inv > 0 else 0
                    tier_month_rows.append({
                        "Month": month,
                        "Investment": _fmt_dollar_commas(inv),
                        "Delivered": f"{delivered:,.0f}",
                        "Prospects": f"{prospects:,.0f}",
                        "Inc. Cust": _range_str(cust_min, cust_max, _fmt_compact_k),
                        "Inc. Rev": _range_str(rev_min, rev_max, _fmt_dollar_compact_m),
                        "CPIx": _range_str(cpix_min, cpix_max, _fmt_dollar_0),
                        "iROAS": _range_str(iroas_min, iroas_max, _fmt_iroas),
                        "% Utilization": f"{_sig_util_by_tier.get(label, 0):.0f}%",
                    })
                st.dataframe(pd.DataFrame(tier_month_rows), hide_index=True, use_container_width=True)
        else:
            for month in _proj_months:
                org_pct = indexes["monthly_organic"].get(month, 1/12) / org_sum if org_sum else 1/3
                inc_pct = indexes["monthly_incremental"].get(month, 1/12) / inc_sum if inc_sum else 1/3

                st.subheader(f"{month} (Organic: {org_pct*100:.1f}%, Incremental: {inc_pct*100:.1f}%)")

                month_rows = []
                for r in visible_ranges:
                    label = r.tier_label
                    inv = float(r.investment) * org_pct
                    delivered = float(r.delivered_volume) * org_pct
                    prospects = float(r.prospects) * org_pct

                    cust_min = float(r.incremental_customers.minimum) * inc_pct
                    cust_max = float(r.incremental_customers.maximum) * inc_pct
                    rev_min = float(r.incremental_revenue.minimum) * inc_pct
                    rev_max = float(r.incremental_revenue.maximum) * inc_pct

                    cpix_min = inv / cust_max if cust_max > 0 else 0
                    cpix_max = inv / cust_min if cust_min > 0 else 0
                    iroas_min = rev_min / inv if inv > 0 else 0
                    iroas_max = rev_max / inv if inv > 0 else 0

                    mcpix_str = "—"
                    miroas_str = "—"
                    if label != _first_tier_label:
                        if _marginal_cpix_values.get(label):
                            mc_vals = _marginal_cpix_values[label]
                            if len(mc_vals) == 1:
                                mcpix_str = _range_str(mc_vals[0] / (1 + _range_adj), mc_vals[0] / (1 - _range_adj), _fmt_dollar_0)
                            else:
                                mcpix_str = _range_str(min(mc_vals), max(mc_vals), _fmt_dollar_0)
                        if _marginal_iroas_values.get(label):
                            mi_vals = _marginal_iroas_values[label]
                            if len(mi_vals) == 1:
                                miroas_str = _range_str(mi_vals[0] * (1 - _range_adj), mi_vals[0] * (1 + _range_adj), _fmt_iroas)
                            else:
                                miroas_str = _range_str(min(mi_vals), max(mi_vals), _fmt_iroas)

                    month_rows.append({
                        "Tiers": label,
                        "Investment": _fmt_dollar_commas(inv),
                        "Delivered": f"{delivered:,.0f}",
                        "Prospects": f"{prospects:,.0f}",
                        "Inc. Cust": _range_str(cust_min, cust_max, _fmt_compact_k),
                        "Inc. Rev": _range_str(rev_min, rev_max, _fmt_dollar_compact_m),
                        "CPIx": _range_str(cpix_min, cpix_max, _fmt_dollar_0),
                        "iROAS": _range_str(iroas_min, iroas_max, _fmt_iroas),
                        "Marginal CPIx": mcpix_str,
                        "Marginal iROAS": miroas_str,
                        "% Utilization": f"{_sig_util_by_tier.get(label, 0):.0f}%",
                    })

                st.dataframe(pd.DataFrame(month_rows), hide_index=True, use_container_width=True)

    except Exception as exc:
        st.warning(f"Could not compute monthly split: {exc}")

    _render_download_button("tab3b_qm")
    tab_nav_buttons(tab_names, 3)


# =============================================================================
# CHARTS TAB (all tiers from Baseline to Maximum Scale)
# =============================================================================
if st.session_state.forecast and active_tab == _charts_tab_idx:
    result = st.session_state.forecast
    # Use ALL tiers (standard + expansion) for charts
    all_ranges = sorted(result["ranges"], key=lambda r: float(r.investment))
    latest_quarter = max(
        (row["campaign_quarter"] for row in st.session_state.selected_history),
        key=quarter_value,
    )

    st.header("Forecast Charts")

    # Build chart dataframe with ALL tiers
    chart_df = pd.DataFrame([
        {
            "Tier": _fmt_dollar_commas(float(row.investment)),
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
    _x_axis = alt.X("Tier:N", sort=tier_order, title="Tier", axis=alt.Axis(labelAngle=-25, labelAlign="right", labelLimit=200, labelOverlap=False))
    # Vertical gridlines for line charts
    _v_rules = alt.Chart(chart_df).mark_rule(color="#e0e0e0", strokeWidth=1).encode(
        x=_x_axis,
    )

    cpix_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#00d4aa").encode(
        x=_x_axis,
        y=alt.Y("CPIx Min:Q", title="CPIx", axis=alt.Axis(format="$~s")),
        y2="CPIx Max:Q",
    )
    cpix_line = alt.Chart(chart_df).mark_line(point=True, color="#00d4aa", strokeWidth=2.5).encode(
        x=_x_axis,
        y=alt.Y("CPIx Midpoint:Q", title="CPIx", axis=alt.Axis(format="$~s")),
        tooltip=["Tier", "CPIx Min", "CPIx Midpoint", "CPIx Max", "Investment"],
    )
    st.altair_chart(
        (_v_rules + cpix_band + cpix_line).properties(title="CPIx increases as investment exceeds Sustainable Scale", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 2: iROAS across all tiers ---
    st.subheader("iROAS by Investment Tier")
    iroas_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#4da6ff").encode(
        x=_x_axis,
        y=alt.Y("iROAS Min:Q", title="iROAS"),
        y2="iROAS Max:Q",
    )
    iroas_line = alt.Chart(chart_df).mark_line(point=True, color="#4da6ff", strokeWidth=2.5).encode(
        x=_x_axis,
        y=alt.Y("iROAS Midpoint:Q", title="iROAS"),
        tooltip=["Tier", "iROAS Min", "iROAS Midpoint", "iROAS Max", "Investment"],
    )
    st.altair_chart(
        (_v_rules + iroas_band + iroas_line).properties(title="iROAS declines with diminishing returns at higher investment", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 3: Incremental Customers across all tiers ---
    st.subheader("Incremental Customers by Investment Tier")
    cust_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#10b981").encode(
        x=_x_axis,
        y=alt.Y("Customers Min:Q", title="Incremental Customers", axis=alt.Axis(format="~s")),
        y2="Customers Max:Q",
    )
    cust_line = alt.Chart(chart_df).mark_line(point=True, color="#10b981", strokeWidth=2.5).encode(
        x=_x_axis,
        y=alt.Y("Customers Midpoint:Q", title="Incremental Customers", axis=alt.Axis(format="~s")),
        tooltip=["Tier", "Customers Min", "Customers Midpoint", "Customers Max", "Investment"],
    )
    st.altair_chart(
        (_v_rules + cust_band + cust_line).properties(title="Customer growth flattens beyond Sustainable Scale (decay curve effect)", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 4: Incremental Revenue across all tiers ---
    st.subheader("Incremental Revenue by Investment Tier")
    rev_band = alt.Chart(chart_df).mark_area(opacity=0.25, color="#8b5cf6").encode(
        x=_x_axis,
        y=alt.Y("Revenue Min:Q", title="Incremental Revenue", axis=alt.Axis(format="$~s")),
        y2="Revenue Max:Q",
    )
    rev_line = alt.Chart(chart_df).mark_line(point=True, color="#8b5cf6", strokeWidth=2.5).encode(
        x=_x_axis,
        y=alt.Y("Revenue Midpoint:Q", title="Incremental Revenue", axis=alt.Axis(format="$~s")),
        tooltip=["Tier", "Revenue Min", "Revenue Midpoint", "Revenue Max", alt.Tooltip("Investment:Q", format="$,.0f")],
    )
    st.altair_chart(
        (_v_rules + rev_band + rev_line).properties(title="Revenue growth mirrors customer decay at higher tiers", height=380),
        use_container_width=True,
    )

    st.divider()

    # --- Chart 5: Investment vs Delivered Volume & Prospects (bar chart) ---
    st.subheader("Delivered Volume & Prospects by Tier")
    vol_col, pros_col = st.columns(2)
    vol_chart = alt.Chart(chart_df).mark_bar(color="#06b6d4", opacity=0.8).encode(
        x=_x_axis,
        y=alt.Y("Delivered:Q", title="Delivered Volume", axis=alt.Axis(format="~s")),
        tooltip=["Tier", alt.Tooltip("Delivered:Q", format=",.0f"), alt.Tooltip("Investment:Q", format="$,.0f")],
    ).properties(title="Delivered Volume (scales linearly with investment)", height=350)
    vol_col.altair_chart(vol_chart, use_container_width=True)

    pros_chart = alt.Chart(chart_df).mark_bar(color="#f59e0b", opacity=0.8).encode(
        x=_x_axis,
        y=alt.Y("Prospects:Q", title="Prospects", axis=alt.Axis(format="~s")),
        tooltip=["Tier", alt.Tooltip("Prospects:Q", format=",.0f"), alt.Tooltip("Investment:Q", format="$,.0f")],
    ).properties(title="Prospects (scales linearly — not curve-affected)", height=350)
    pros_col.altair_chart(pros_chart, use_container_width=True)

    st.divider()

    # --- Chart 6: Investment amount by tier (bar chart) ---
    st.subheader("Investment by Tier")
    _tier_type_map = {
        _fmt_dollar_commas(float(r.investment)): "Extension"
        if "Incremental" in r.tier_label or "Maximum" in r.tier_label
        else "Standard"
        for r in all_ranges
    }
    chart_df["Tier Type"] = chart_df["Tier"].map(_tier_type_map).fillna("Standard")
    invest_chart = alt.Chart(chart_df).mark_bar(
        cornerRadiusTopLeft=4, cornerRadiusTopRight=4
    ).encode(
        x=_x_axis,
        y=alt.Y("Investment:Q", title="Investment", axis=alt.Axis(format="$~s")),
        color=alt.Color("Tier Type:N", scale=alt.Scale(
            domain=["Standard", "Extension"], range=["#3b82f6", "#f97316"]
        ), title="Type"),
        tooltip=["Tier", alt.Tooltip("Investment:Q", format="$,.0f"), "Tier Type"],
    ).properties(title="Investment tiers — standard (blue) vs extension (orange)", height=380)
    st.altair_chart(invest_chart, use_container_width=True)

    # Export charts as PNG for the Excel workbook
    _chart_images = []
    _chart_defs = [
        ("CPIx by Investment Tier", (_v_rules + cpix_band + cpix_line).properties(width=700, height=380)),
        ("iROAS by Investment Tier", (_v_rules + iroas_band + iroas_line).properties(width=700, height=380)),
        ("Incremental Customers", (_v_rules + cust_band + cust_line).properties(width=700, height=380)),
        ("Incremental Revenue", (_v_rules + rev_band + rev_line).properties(width=700, height=380)),
        ("Delivered Volume", vol_chart.properties(width=700, height=350)),
        ("Prospects", pros_chart.properties(width=700, height=350)),
        ("Investment by Tier", invest_chart.properties(width=700, height=380)),
    ]
    for _c_title, _c_obj in _chart_defs:
        try:
            _png = _c_obj.to_dict()
            import json as _json_chart
            from io import BytesIO as _BytesIO_chart
            try:
                import vl_convert as vlc
                _png_bytes = vlc.vegalite_to_png(vl_spec=_json_chart.dumps(_png), scale=2)
                _chart_images.append((_c_title, _png_bytes))
            except Exception:
                pass
        except Exception:
            pass

    _render_download_button("charts", chart_images=_chart_images if _chart_images else None)
    tab_nav_buttons(tab_names, _charts_tab_idx)



# =============================================================================
# TEMPORARY QA TAB — PROJECTION CALCULATIONS
# Read-only display of the same in-memory projections used to create forecast
# ranges. This is intentionally a presentation layer only.
# =============================================================================
if st.session_state.forecast and active_tab == _qa_tab_idx:
    result = st.session_state.forecast
    # QA mirrors the Excel Projection Calculations sheet: show Sustainable
    # Scale plus every extension tier through Maximum Scale (+25%).
    qa_visible_projections = list(result["projections"])
    qa_history = sorted(
        st.session_state.selected_history,
        key=lambda row: quarter_value(row["campaign_quarter"]),
    )
    qa_history_by_quarter = {
        row["campaign_quarter"]: row for row in qa_history
    }
    qa_quarters = sorted(
        {row.historical_quarter for row in qa_visible_projections},
        key=quarter_value,
    )

    def _qa_float(value):
        return float(value) if value is not None else None

    def _qa_actual_frame(rows):
        return pd.DataFrame([
            {
                "Tier": row.tier_label,
                "Investment": _qa_float(row.investment),
                "Delivered Volume": _qa_float(row.delivered_volume),
                "Prospects": _qa_float(row.prospects),
                "Inc. Customers": _qa_float(row.incremental_customers),
                "Incremental Revenue": _qa_float(row.incremental_revenue),
                "CPIx": _qa_float(row.cpix),
                "iROAS": _qa_float(row.iroas),
                "Marginal CPIx": _qa_float(row.marginal_cpix),
                "Marginal iROAS": _qa_float(row.marginal_iroas),
                "New Signal Utilization": _qa_float(row.new_signal_utilization),
                "Adjustment Factor": _qa_float(row.adjustment_factor),
                "Marginal Inc. Customers": _qa_float(row.marginal_incremental_customers),
            }
            for row in sorted(rows, key=lambda item: float(item.investment))
        ])

    def _qa_scenario_frame(rows):
        return pd.DataFrame([
            {
                "Tier": row.tier_label,
                "Investment": _qa_float(row.investment),
                "Inc. Customers": _qa_float(row.incremental_customers),
                "Incremental Revenue": _qa_float(row.incremental_revenue),
                "CPIx": _qa_float(row.cpix),
                "iROAS": _qa_float(row.iroas),
                "Marginal CPIx": _qa_float(row.marginal_cpix),
                "Marginal iROAS": _qa_float(row.marginal_iroas),
            }
            for row in sorted(rows, key=lambda item: float(item.investment))
        ])

    st.header("Projection Calculations (QA)")
    st.caption(
        "Temporary, read-only QA view. These tables use the exact in-memory "
        "projections that create the forecast ranges; they do not recalculate "
        "or change the forecast."
    )

    qa_input_rows = [
        {"Input": "Using Data From", "Value": st.session_state.get("selected_planning_quarter", "—")},
        {"Input": "Projection Quarter", "Value": st.session_state.get("projection_quarter", "—")},
        {"Input": "Projection Mode", "Value": st.session_state.get("projection_mode", "Quarterly")},
        {"Input": "Selected Historical Quarters", "Value": ", ".join(qa_quarters)},
        {"Input": "Current Budget", "Value": _qa_float(st.session_state.get("current_budget"))},
        {"Input": "Forecast CPM", "Value": _qa_float(st.session_state.get("cpm"))},
        {"Input": "Historical Prospect Frequency", "Value": sum(float(row["frequency"]) for row in qa_history) / len(qa_history) if qa_history else None},
        {"Input": "Current Signal Utilization", "Value": _qa_float(st.session_state.get("signal_utilization"))},
        {"Input": "Max Reach", "Value": _qa_float(st.session_state.get("max_reach"))},
        {"Input": "Frequency at Max Reach", "Value": _qa_float(st.session_state.get("frequency_at_max"))},
        {"Input": "One-Quarter Range Adjustment (%)", "Value": _qa_float(st.session_state.get("range_percent_input", 10))},
        {"Input": "Range Method", "Value": result.get("method", "—")},
    ]
    st.dataframe(pd.DataFrame(qa_input_rows), hide_index=True, use_container_width=True)

    qa_tabs = st.tabs([*qa_quarters, "KPI Minimums", "KPI Maximums", "Final Ranges"])
    for qa_tab, quarter in zip(qa_tabs[:len(qa_quarters)], qa_quarters):
        with qa_tab:
            historical_row = qa_history_by_quarter.get(quarter, {})
            st.caption(
                f"Historical CPIx: {money(historical_row.get('cpix', 0))} | "
                f"Average incremental revenue per customer: "
                f"{money(historical_row.get('average_incremental_revenue', 0))}"
            )
            quarter_rows = [
                row for row in qa_visible_projections
                if row.historical_quarter == quarter
            ]
            actual_tab, *scenario_tabs = st.tabs(
                ["Actual Historical Performance"] + [
                    name for name, _, _ in result.get("improvements", [])
                ]
            )
            with actual_tab:
                st.dataframe(_qa_actual_frame(quarter_rows), hide_index=True, use_container_width=True)
            for scenario_tab, (scenario_name, scenario_factor, scenario_rows) in zip(
                scenario_tabs, result.get("improvements", [])
            ):
                with scenario_tab:
                    st.caption(f"Improvement factor: {float(scenario_factor) * 100:.1f}%")
                    st.dataframe(
                        _qa_scenario_frame([
                            row for row in scenario_rows
                            if row.historical_quarter == quarter
                        ]),
                        hide_index=True,
                        use_container_width=True,
                    )

    qa_metric_fields = [
        ("Investment", "investment"),
        ("Delivered Volume", "delivered_volume"),
        ("Prospects", "prospects"),
        ("Inc. Customers", "incremental_customers"),
        ("Incremental Revenue", "incremental_revenue"),
        ("CPIx", "cpix"),
        ("iROAS", "iroas"),
        ("Marginal CPIx", "marginal_cpix"),
        ("Marginal iROAS", "marginal_iroas"),
        ("Marginal Inc. Customers", "marginal_incremental_customers"),
    ]
    qa_by_tier = {}
    for row in qa_visible_projections:
        qa_by_tier.setdefault(row.tier_label, []).append(row)

    def _qa_bound_frame(bound):
        output_rows = []
        for label, tier_rows in sorted(
            qa_by_tier.items(),
            key=lambda item: float(item[1][0].investment),
        ):
            output_row = {"Tier": label}
            for display_name, field in qa_metric_fields:
                values = [
                    _qa_float(getattr(row, field))
                    for row in tier_rows
                    if getattr(row, field) is not None
                ]
                output_row[display_name] = bound(values) if values else None
            output_rows.append(output_row)
        return pd.DataFrame(output_rows)

    with qa_tabs[-3]:
        st.caption("Metric-by-metric minimum across the selected historical-quarter projection tables.")
        st.dataframe(_qa_bound_frame(min), hide_index=True, use_container_width=True)
    with qa_tabs[-2]:
        st.caption("Metric-by-metric maximum across the selected historical-quarter projection tables.")
        st.dataframe(_qa_bound_frame(max), hide_index=True, use_container_width=True)
    with qa_tabs[-1]:
        if result.get("method") == "single-quarter-exact":
            st.caption(
                "One historical quarter is selected, so Final Ranges equal the KPI "
                "Minimums and KPI Maximums for that quarter."
            )
        else:
            st.caption(
                "Multiple historical quarters are selected. Final Ranges use the "
                "minimum and maximum across all quarter projections."
            )
        st.caption(
            f"Historic Prospect Frequency = {historical_frequency:.1f}x"
        )
        st.dataframe(
            pd.DataFrame([
                {
                    "Tier": row.tier_label,
                    "Investment": _qa_float(row.investment),
                    "Delivered Volume": _qa_float(row.delivered_volume),
                    "Prospects": _qa_float(row.prospects),
                    "Inc. Customers Min": _qa_float(row.incremental_customers.minimum),
                    "Inc. Customers Max": _qa_float(row.incremental_customers.maximum),
                    "Incremental Revenue Min": _qa_float(row.incremental_revenue.minimum),
                    "Incremental Revenue Max": _qa_float(row.incremental_revenue.maximum),
                    "CPIx Min": _qa_float(row.cpix.minimum),
                    "CPIx Max": _qa_float(row.cpix.maximum),
                    "iROAS Min": _qa_float(row.iroas.minimum),
                    "iROAS Max": _qa_float(row.iroas.maximum),
                }
                for row in result["ranges"]            ]),
            hide_index=True,
            use_container_width=True,
        )

    tab_nav_buttons(tab_names, _qa_tab_idx)