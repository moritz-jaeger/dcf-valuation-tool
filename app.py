"""
app.py
------
Valuation Engine — "The Pitchbook"
Editorial light-paper theme. 5-chapter guided DCF wizard.
"""

import copy
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from typing import Any

from data_fetcher   import fetch_financial_data
from fcf_calculator import calculate_fcf
from assumptions    import build_assumptions
from dcf_engine     import run_dcf
from sensitivity    import build_sensitivity
from risk           import assess_risk


# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Valuation Engine",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── Design system ────────────────────────────────────────────────────────────
# "The Pitchbook" — warm paper editorial theme

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Serif:ital,wght@0,400;0,500;0,600;1,400&display=swap');

/* ── Tokens ─────────────────────────────────────────────── */
:root {
  --paper:       #F5F1E8;
  --paper-2:     #EDE7D6;
  --paper-3:     #E4DCCA;
  --ink:         #0B1A2B;
  --ink-2:       #2B3B4F;
  --ink-3:       #5C6B7D;
  --rule:        #D9D1BD;
  --rule-2:      #C4B995;
  --accent:      #2140C7;
  --accent-2:    #4E66D7;
  --accent-dim:  rgba(33,64,199,0.10);
  --accent-bdr:  rgba(33,64,199,0.25);
  --gold:        #B7892C;
  --moss:        #3B6B3B;
  --rust:        #A33A2A;
  --sans:        'Inter', -apple-system, sans-serif;
  --serif:       'IBM Plex Serif', 'Georgia', serif;
  --mono:        'IBM Plex Mono', 'SF Mono', monospace;
}

/* ── Global ─────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {
  background: var(--paper) !important;
  color: var(--ink) !important;
  background-image: radial-gradient(rgba(11,26,43,0.018) 1px, transparent 1px) !important;
  background-size: 3px 3px !important;
}
html, body, input, button, textarea, select,
.stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown div {
  font-family: var(--sans) !important;
  color: var(--ink) !important;
}
.stMarkdown p, .stMarkdown li { color: var(--ink-2) !important; }
[data-testid="stText"],
[data-testid="stCaption"] p,
[data-testid="stCaptionContainer"] p { color: var(--ink-3) !important; }
.main .block-container { padding: 0 2.5rem 4rem; max-width: 1280px; }

/* ── Hide Streamlit chrome + sidebar ────────────────────── */
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* ── Topbar & spine ─────────────────────────────────────── */
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 22px 0 0;
}
.brand {
  font-family: var(--serif); font-style: italic; font-size: 17px;
  color: var(--ink); letter-spacing: -0.01em;
}
.brand b {
  font-style: normal; font-weight: 600; font-family: var(--sans);
  letter-spacing: 0.14em; text-transform: uppercase; font-size: 11px;
  color: var(--ink-2); margin-right: 10px; vertical-align: middle;
}
.folio {
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.12em;
  color: var(--ink-3); text-transform: uppercase;
}
.page-spine {
  height: 2px; background: var(--rule); margin: 18px 0 0;
  position: relative; overflow: hidden;
}
.page-spine .fill {
  position: absolute; inset: 0 auto 0 0; background: var(--ink);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

/* ── Buttons ────────────────────────────────────────────── */
.stButton > button {
  background: var(--ink) !important;
  color: var(--paper) !important;
  border: 1px solid var(--ink) !important;
  border-radius: 0 !important;
  font-weight: 600 !important;
  font-size: 0.93rem !important;
  letter-spacing: 0.02em !important;
  padding: 13px 24px !important;
  transition: background 0.18s, border-color 0.18s, transform 0.12s !important;
}
.stButton > button:hover {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
}
.stButton > button:active { transform: translateY(1px) !important; }

/* Ghost button wrapper */
.ghost-btn .stButton > button {
  background: transparent !important;
  color: var(--ink) !important;
}
.ghost-btn .stButton > button:hover {
  background: var(--ink) !important;
  color: var(--paper) !important;
}

/* Chip button wrapper */
.chip-btn .stButton > button {
  background: transparent !important;
  color: var(--ink) !important;
  font-family: var(--mono) !important;
  font-size: 12px !important;
  letter-spacing: 0.08em !important;
  padding: 8px 16px !important;
}
.chip-btn .stButton > button:hover {
  background: var(--ink) !important;
  color: var(--paper) !important;
}

/* ── Sliders ────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
  background: var(--accent) !important;
  border: 2px solid var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(33,64,199,0.12) !important;
}
[data-testid="stSlider"] label { color: var(--ink-2) !important; }

/* ── Number + text inputs ────────────────────────────────── */
[data-testid="stNumberInput"] input {
  color: var(--ink) !important;
  background: white !important;
  border: 1px solid var(--rule-2) !important;
  border-radius: 0 !important;
  font-family: var(--mono) !important;
}
[data-testid="stNumberInput"] input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-dim) !important;
  outline: none !important;
}
[data-testid="stTextInput"] input {
  font-family: var(--serif) !important;
  font-size: 1.75rem !important;
  line-height: 1.2 !important;
  color: var(--ink) !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid var(--ink) !important;
  border-radius: 0 !important;
  text-align: center !important;
  letter-spacing: -0.02em !important;
  padding: 8px 0 10px !important;
  box-shadow: none !important;
}
[data-testid="stTextInput"] input:focus {
  border-bottom-color: var(--accent) !important;
  box-shadow: none !important;
  outline: none !important;
}
[data-testid="stTextInput"] input::placeholder { color: var(--rule-2) !important; }
[data-testid="stRadio"] label, [data-testid="stRadio"] p { color: var(--ink-2) !important; }

/* ── Expanders ──────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: white !important;
  border: 1px solid var(--rule) !important;
  border-radius: 0 !important;
}
[data-testid="stExpander"] summary { color: var(--ink) !important; font-weight: 600 !important; }

/* ── Tabs ───────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] { color: var(--ink-3) !important; font-weight: 500 !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--ink) !important; font-weight: 600 !important;
  border-bottom-color: var(--accent) !important;
}

/* ── Typography ─────────────────────────────────────────── */
.eyebrow {
  font-family: var(--mono); font-size: 11px; letter-spacing: 0.16em;
  text-transform: uppercase; color: var(--ink-3); font-weight: 500; display: block;
}
.display {
  font-family: var(--serif); font-weight: 400;
  font-size: clamp(2.6rem, 4.5vw, 3.8rem);
  line-height: 1.04; letter-spacing: -0.025em; color: var(--ink);
}
.display-hero {
  font-family: var(--serif); font-weight: 400;
  font-size: clamp(3rem, 5.5vw, 4.5rem);
  line-height: 1.02; letter-spacing: -0.03em; color: var(--ink);
}
.display em, .display-hero em { font-style: italic; color: var(--accent); }
.lede {
  font-family: var(--serif); font-size: 1.2rem; line-height: 1.5;
  color: var(--ink-2); font-style: italic; max-width: 52ch;
}
.num { font-family: var(--mono); font-feature-settings: "tnum" 1; letter-spacing: -0.01em; }
.meta { font-family: var(--mono); font-size: 11px; color: var(--ink-3); letter-spacing: 0.08em; text-transform: uppercase; }

/* ── KPI cards ──────────────────────────────────────────── */
.kpi-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.kpi-card {
  flex: 1; min-width: 140px; background: white;
  border: 1px solid var(--rule); border-top: 2px solid var(--ink); padding: 14px 18px;
  transition: border-top-color 0.18s;
}
.kpi-card:hover { border-top-color: var(--accent); }
.kpi-lbl {
  font-family: var(--mono); font-size: 10px; font-weight: 700; color: var(--ink-3);
  text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 7px;
}
.kpi-val { font-family: var(--mono); font-size: 1.45rem; font-weight: 700; color: var(--ink); letter-spacing: -0.02em; }
.kpi-sub { font-size: 0.7rem; color: var(--ink-3); margin-top: 5px; }

/* ── Section headers ────────────────────────────────────── */
.sec-wrap { display: flex; align-items: center; gap: 10px; margin: 2rem 0 0.9rem; }
.sec-bar  { width: 3px; height: 18px; background: var(--accent); flex-shrink: 0; }
.sec      { font-size: 0.78rem; font-weight: 700; color: var(--ink-2); text-transform: uppercase; letter-spacing: 0.1em; }

/* ── Tables ─────────────────────────────────────────────── */
.htable { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.htable th {
  background: var(--paper-2); color: var(--ink-3);
  font-family: var(--mono); font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.09em; padding: 9px 14px; text-align: right;
  border-bottom: 1px solid var(--rule);
}
.htable th:first-child { text-align: left; }
.htable td {
  padding: 9px 14px; color: var(--ink); border-bottom: 1px solid var(--rule); text-align: right;
}
.htable td:first-child { text-align: left; color: var(--ink-2); font-size: 0.82rem; }
.htable tr:last-child td { border-bottom: none; }
.htable tr:hover td { background: rgba(33,64,199,0.04); }
.pos   { color: var(--moss)   !important; }
.neg   { color: var(--rust)   !important; }
.muted { color: var(--ink-3); }
.acc   { color: var(--accent) !important; font-weight: 600; }

/* ── Dividers ───────────────────────────────────────────── */
.hr      { border: none; border-top: 1px solid var(--rule);  margin: 2rem 0; }
.hr-dark { border: none; border-top: 1px solid var(--ink);   margin: 0.75rem 0; }

/* ── Number stats (editorial column) ───────────────────── */
.num-stat       { padding: 20px 0; border-bottom: 1px solid var(--rule); }
.num-stat.last  { border-bottom: none; }
.num-stat-lbl   { font-family: var(--mono); font-size: 10px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 6px; }
.num-stat-val   { font-family: var(--mono); font-size: 2.4rem; font-weight: 500; letter-spacing: -0.02em; color: var(--ink); margin-bottom: 6px; }
.num-stat-hint  { font-family: var(--serif); font-style: italic; font-size: 13.5px; color: var(--ink-3); line-height: 1.4; }

/* ── TOC entries ─────────────────────────────────────────── */
.toc-ch    { font-family: var(--mono); font-size: 10px; color: var(--ink-3); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 8px; }
.toc-hr    { height: 1px; background: var(--ink); margin-bottom: 10px; }
.toc-title { font-family: var(--serif); font-size: 22px; font-weight: 500; letter-spacing: -0.015em; margin-bottom: 6px; color: var(--ink); }
.toc-body  { font-size: 14px; color: var(--ink-3); line-height: 1.5; }

/* ── Scenario cards ─────────────────────────────────────── */
.scenario-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; border: 1px solid var(--ink); margin-bottom: 2.5rem; }
.scenario-card { padding: 28px 24px; }
.scenario-card + .scenario-card { border-left: 1px solid var(--ink); }
.scenario-card.base { background: var(--paper-2); }
.scenario-lbl  { font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 12px; }
.scenario-val  { font-family: var(--mono); font-size: 2.6rem; font-weight: 500; letter-spacing: -0.025em; margin-bottom: 6px; color: var(--ink); }
.scenario-delta { font-family: var(--mono); font-size: 12px; margin-bottom: 14px; }
.scenario-note { font-family: var(--serif); font-style: italic; font-size: 13.5px; color: var(--ink-3); line-height: 1.5; }

/* ── Model summary rows ─────────────────────────────────── */
.model-row        { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--rule); }
.model-row.last   { border-bottom: none; }
.model-row-lbl    { font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-3); }
.model-row-val    { font-family: var(--mono); font-size: 14px; font-weight: 400; color: var(--ink); }
.model-row-val.acc { color: var(--accent); font-weight: 600; }

/* ── Risk cards ─────────────────────────────────────────── */
.risk-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 4px; }
.risk-card { background: white; border: 1px solid var(--rule); padding: 14px 16px; }
.risk-card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.risk-dot  { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.risk-name { font-family: var(--mono); font-size: 10px; font-weight: 700; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.09em; }
.risk-val  { font-family: var(--mono); font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 4px; }
.risk-note { font-size: 0.72rem; color: var(--ink-2); line-height: 1.5; margin-bottom: 5px; }
.risk-thresh { font-size: 0.62rem; color: var(--ink-3); line-height: 1.4; }

/* ── Narrative box ──────────────────────────────────────── */
.narrative {
  background: white; border: 1px solid var(--rule); border-left: 3px solid var(--accent);
  padding: 16px 20px; margin-bottom: 1.5rem;
  font-size: 0.87rem; color: var(--ink-2); line-height: 1.7;
}
.narrative strong { color: var(--ink); }

/* ── Assumption strip ───────────────────────────────────── */
.assumption-strip {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  background: white; border: 1px solid var(--rule); border-left: 3px solid var(--accent);
  padding: 10px 16px; margin-bottom: 12px;
}
.astrip-label { font-family: var(--mono); font-size: 10px; font-weight: 700; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.09em; margin-right: 4px; }
.astrip-chip  { background: var(--paper-2); border: 1px solid var(--rule-2); padding: 3px 10px; font-family: var(--mono); font-size: 0.75rem; font-weight: 600; color: var(--accent); }
.astrip-sep   { color: var(--rule-2); font-size: 0.75rem; }

/* ── WACC preview box ───────────────────────────────────── */
.wacc-box { background: white; border: 1px solid var(--rule); padding: 16px 20px; margin-top: 12px; display: flex; align-items: center; gap: 28px; flex-wrap: wrap; }
.wacc-val    { font-family: var(--mono); font-size: 2rem; font-weight: 500; color: var(--accent); }
.wacc-detail { font-size: 0.8rem; color: var(--ink-2); line-height: 1.7; }

/* ── Animations ─────────────────────────────────────────── */
@keyframes riseIn {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.rise  { animation: riseIn 0.6s cubic-bezier(0.22,1,0.36,1) both; }
.rise1 { animation-delay: 0.08s; }
.rise2 { animation-delay: 0.16s; }
.rise3 { animation-delay: 0.24s; }
.rise4 { animation-delay: 0.32s; }
</style>
"""


# ─── Session state ────────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults: dict[str, Any] = {
        "chapter":      0,
        "ticker":       "",
        "data":         None,
        "dcf":          None,
        "sens":         None,
        "saved_growth": None,
        "saved_margin": None,
        "saved_tgr":    0.025,
        "saved_rfr":    0.0425,
        "saved_erp":    0.045,
        "saved_beta":   None,
        "saved_kd":     0.04,
        "saved_tc":     0.21,
        "saved_eqw":    0.90,
        "saved_dew":    0.10,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def _load_ticker_data(symbol: str) -> dict[str, Any]:
    fin         = fetch_financial_data(symbol)
    fcf         = calculate_fcf(fin)
    assum       = build_assumptions(symbol, fin)
    risk_result = assess_risk(fin, fcf)

    t    = yf.Ticker(symbol)
    hist = pd.DataFrame()
    try:
        hist = t.history(period="1y")
    except Exception:
        pass

    mkt = fin.get("market_data", {})
    company_info = {
        "name":     mkt.get("name")     or symbol,
        "sector":   mkt.get("sector")   or "N/A",
        "industry": mkt.get("industry") or "N/A",
    }

    price_data: dict[str, Any] = {"dates": [], "prices": []}
    try:
        if not hist.empty:
            close = hist["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            price_data = {
                "dates":  [str(idx.date()) for idx in hist.index],
                "prices": [float(v) for v in close.tolist()],
            }
    except Exception:
        pass

    return {
        "fin": fin, "fcf": fcf, "assum": assum,
        "risk": risk_result, "company_info": company_info,
        "price_data": price_data,
    }


# ─── Formatters ───────────────────────────────────────────────────────────────

def _bil(v: float | None) -> str:
    if v is None:      return "—"
    if abs(v) >= 1e12: return f"${v/1e12:.2f}T"
    if abs(v) >= 1e9:  return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:  return f"${v/1e6:.1f}M"
    return f"${v:,.0f}"

def _pct(v: float | None, dp: int = 2) -> str:
    if v is None: return "—"
    return f"{v:.{dp}%}"

def _px(v: float | None) -> str:
    if v is None: return "—"
    return f"${v:,.2f}"

def _x(v: float | None) -> str:
    if v is None: return "—"
    return f"{v:.2f}×"

def _val_cls(v: float | None) -> str:
    if v is None or v == 0: return "muted"
    return "pos" if v > 0 else "neg"


# ─── HTML helpers ─────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="kpi-card">'
            f'<div class="kpi-lbl">{label}</div>'
            f'<div class="kpi-val">{value}</div>{sub_html}</div>')

def _kpi_row(items: list[tuple]) -> None:
    html = '<div class="kpi-row">'
    for item in items:
        label, value = item[0], item[1]
        sub = item[2] if len(item) > 2 else ""
        html += _kpi(label, value, sub)
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def _htable(headers: list[str], rows: list[list], highlight_last: bool = False) -> None:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for i, row in enumerate(rows):
        is_last = i == len(rows) - 1
        tds = ""
        for j, cell in enumerate(row):
            if j == 0:
                tds += f"<td>{cell}</td>"
            else:
                if str(cell).startswith("<"):
                    if highlight_last and is_last and j == len(row) - 1:
                        tds += f'<td><span class="num acc">{cell}</span></td>'
                    else:
                        tds += f"<td>{cell}</td>"
                else:
                    if highlight_last and is_last and j == len(row) - 1:
                        tds += f'<td><span class="num acc">{cell}</span></td>'
                    else:
                        tds += f'<td><span class="num">{cell}</span></td>'
        body += f"<tr>{tds}</tr>"
    st.markdown(
        f'<table class="htable"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>',
        unsafe_allow_html=True,
    )

def _sec(text: str) -> None:
    st.markdown(
        f'<div class="sec-wrap"><div class="sec-bar"></div><div class="sec">{text}</div></div>',
        unsafe_allow_html=True,
    )

def _hr() -> None:
    st.markdown('<hr class="hr">', unsafe_allow_html=True)


# ─── Chrome helpers ───────────────────────────────────────────────────────────

def _chrome(chapter: int | str | None = None, total: int = 4, progress: float = 0.0) -> None:
    """Render the editorial top bar + progress spine."""
    if chapter is not None:
        ch_str = str(chapter).zfill(2) if isinstance(chapter, int) else chapter
        folio = f"CH · {ch_str} / {str(total).zfill(2)}"
    else:
        folio = "—"
    pct = min(100, max(0, progress * 100))
    st.markdown(f"""
    <div class="topbar">
      <div class="brand"><b>Valuation Engine</b> <span>a quarterly-grade pitchbook</span></div>
      <div class="folio">{folio}</div>
      <div style="min-width:200px;"></div>
    </div>
    <div class="page-spine">
      <div class="fill" style="width:{pct:.0f}%"></div>
    </div>
    <div style="height:40px"></div>
    """, unsafe_allow_html=True)


def _back_link(label: str = "← Back") -> bool:
    """Render a ghost-style back button. Returns True if clicked."""
    with st.container():
        st.markdown('<div class="ghost-btn" style="display:inline-block;">', unsafe_allow_html=True)
        clicked = st.button(label, key=f"back_{st.session_state.chapter}")
        st.markdown("</div>", unsafe_allow_html=True)
    return clicked


# ─── Risk descriptions ────────────────────────────────────────────────────────

_RISK_DESC: dict[str, str] = {
    "Leverage  (Debt / EBIT)":               "How many years of operating profit to repay all debt — lower is safer.",
    "Interest Coverage  (EBIT / Interest)":  "Whether earnings comfortably cover interest payments.",
    "FCF Volatility  (σ of FCF/EBIT)":       "How consistent free cash flow is relative to earnings.",
    "Revenue Consistency  (σ of YoY growth)":"Whether revenue grows steadily.",
    "Debt Trend  (Total Debt CAGR)":          "Whether total debt is rising or falling.",
    "FCF Trend  (normalised slope)":          "Whether free cash flow is improving or deteriorating.",
}


# ─── Plotly theme for paper background ───────────────────────────────────────

_PAPER_LAYOUT = dict(
    plot_bgcolor="#F5F1E8",
    paper_bgcolor="#F5F1E8",
    font=dict(family="Inter, sans-serif", color="#0B1A2B"),
)

_PAPER_XAXIS = dict(
    showgrid=False, zeroline=False,
    tickfont=dict(size=10, color="#5C6B7D"),
    color="#5C6B7D",
)

_PAPER_YAXIS = dict(
    showgrid=True, gridcolor="#D9D1BD", zeroline=False,
    tickfont=dict(size=10, color="#5C6B7D"),
    color="#5C6B7D",
)


# ─── Chapter 0: Landing ───────────────────────────────────────────────────────

def _render_landing() -> None:
    st.markdown("""
    <div style="padding: 22px 0 0;">
      <div class="topbar">
        <div class="brand"><b>Valuation Engine</b> <span>a quarterly-grade pitchbook</span></div>
        <div class="folio">—</div>
        <div style="min-width:200px;"></div>
      </div>
      <div class="page-spine"><div class="fill" style="width:0%"></div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="rise">
      <span class="eyebrow">Issue № 01 · Spring 2026</span>
    </div>
    <div class="display-hero rise rise1" style="max-width:18ch; margin: 20px 0 20px;">
      What is a company <em>actually</em> worth?
    </div>
    <p class="lede rise rise2" style="margin-bottom: 48px;">
      A guided, four-chapter valuation you can finish in two minutes.
      Bring a US ticker, bring your view of the business, leave with a defensible number.
    </p>
    """, unsafe_allow_html=True)

    # Ticker input
    st.markdown("""
    <div class="rise rise3">
      <div class="meta" style="margin-bottom: 12px; display:block;">Enter a ticker to begin</div>
    </div>
    """, unsafe_allow_html=True)

    inp_col, btn_col, _ = st.columns([3, 1.2, 3])
    with inp_col:
        ticker_input = st.text_input(
            "ticker",
            placeholder="AAPL",
            label_visibility="collapsed",
            key="landing_ticker",
        ).upper().strip()

    with btn_col:
        st.markdown("<div style='height:42px'></div>", unsafe_allow_html=True)
        go_clicked = st.button("Begin →", use_container_width=True, key="landing_go")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Quick picks
    st.markdown("""
    <div class="meta rise rise4" style="margin-bottom:10px;">Or try one</div>
    """, unsafe_allow_html=True)
    c1, c2, c3, _, _, _, _, _ = st.columns([1, 1, 1, 1, 1, 1, 1, 1])
    qp_clicked = None
    for col, sym in [(c1, "AAPL"), (c2, "NVDA"), (c3, "TSLA")]:
        with col:
            st.markdown('<div class="chip-btn">', unsafe_allow_html=True)
            if st.button(sym, key=f"qp_{sym}"):
                qp_clicked = sym
            st.markdown("</div>", unsafe_allow_html=True)

    # Handle submissions
    target = None
    if go_clicked and ticker_input:
        target = ticker_input
    elif go_clicked and not ticker_input:
        st.error("Please enter a ticker symbol.")
    elif qp_clicked:
        target = qp_clicked

    if target:
        with st.spinner(f"Fetching data for {target}…"):
            data = _load_ticker_data(target)
        if data["fin"].get("market_data", {}).get("current_price") is None:
            st.error(f"Could not find **{target}**. Check the symbol and try again.")
        else:
            # Pre-fill saved defaults from fetched assumptions
            assum = data["assum"]
            mkt   = data["fin"].get("market_data", {})
            st.session_state.saved_beta   = mkt.get("beta") or 1.0
            st.session_state.saved_rfr    = (assum.get("risk_free_rate", {}).get("value")      or 0.0425)
            st.session_state.saved_erp    = (assum.get("equity_risk_premium", {}).get("value") or 0.045)
            st.session_state.saved_kd     = (assum.get("cost_of_debt", {}).get("value")        or 0.04)
            st.session_state.saved_tc     = (assum.get("effective_tax_rate", {}).get("value")  or 0.21)
            cs = assum.get("capital_structure") or {}
            st.session_state.saved_eqw    = cs.get("equity_weight", 0.90)
            st.session_state.saved_dew    = cs.get("debt_weight",   0.10)
            st.session_state.saved_margin = (assum.get("ebit_margin_avg", {}).get("value") or 0.20)
            # Default growth from analyst estimates
            arg = assum.get("analyst_revenue_growth", {})
            g = (arg.get("next_year", {}).get("value")
                 or arg.get("current_year", {}).get("value")
                 or assum.get("revenue_cagr_3yr", {}).get("value")
                 or 0.065)
            st.session_state.saved_growth = g
            st.session_state.update(ticker=target, data=data, chapter=1)
            st.rerun()

    # TOC
    st.markdown("<div style='height:72px'></div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    toc = [
        ("01", "Snapshot",             "Who you're buying. Price, size, and three numbers that set the stakes."),
        ("02", "Growth",               "Shape the revenue trajectory you believe in."),
        ("03", "Profitability",        "Where margins settle and how to model steady-state cash."),
        ("04", "Verdict",              "Fair value, framed three ways. Bear, base, bull — you decide what to buy."),
    ]
    for col, (num, title, body) in zip([c1, c2, c3, c4], toc):
        with col:
            st.markdown(f"""
            <div class="toc-entry rise rise{int(num) % 4 + 1}">
              <div class="toc-ch">CH · {num}</div>
              <div class="toc-hr"></div>
              <div class="toc-title">{title}</div>
              <div class="toc-body">{body}</div>
            </div>
            """, unsafe_allow_html=True)


# ─── Chapter 1: Snapshot ─────────────────────────────────────────────────────

def _render_chapter_snapshot() -> None:
    data = st.session_state.data
    fin  = data["fin"]
    mkt  = fin.get("market_data", {})
    ci   = data["company_info"]
    pd_  = data["price_data"]
    risk = data["risk"]
    ticker = st.session_state.ticker

    _chrome(chapter=1, total=4, progress=0.25)

    # Back link row
    back_col, _ = st.columns([1, 5])
    with back_col:
        st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
        if st.button("← New ticker", key="back_1"):
            st.session_state.update(chapter=0, ticker="", data=None, dcf=None, sens=None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # Two-column editorial layout
    left, right = st.columns([1.1, 1], gap="large")

    with left:
        cur     = mkt.get("current_price")
        prices  = pd_.get("prices", [])
        up      = (prices[-1] >= prices[0]) if len(prices) >= 2 else True
        pct_chg = ((prices[-1] / prices[0] - 1)) if len(prices) >= 2 else 0.0
        chg_str = f"{'up' if up else 'down'}"
        chg_color = "var(--moss)" if up else "var(--rust)"
        name_short = ci.get("name", ticker).replace(" Inc.", "").replace(" Corp.", "").replace(" Corporation", "").rstrip(".")

        st.markdown(f"""
        <span class="eyebrow rise" style="display:block; margin-bottom:16px;">Chapter one · The company</span>
        <div class="display rise rise1" style="margin-bottom:20px;">
          You're looking at <em>{name_short}</em>.
        </div>
        <p class="lede rise rise2" style="margin-bottom:28px;">
          {ci.get('sector', '')}. Trading at
          <b class="num" style="font-style:normal;color:var(--ink);">{_px(cur)}</b>,
          {chg_str}
          <b class="num" style="font-style:normal;color:{chg_color};">{abs(pct_chg):.1%}</b>
          over the last trading year.
        </p>
        """, unsafe_allow_html=True)

        # Sparkline
        dates  = pd_.get("dates", [])
        if dates and prices:
            line_c = "#3B6B3B" if up else "#A33A2A"
            fill_c = "rgba(59,107,59,0.07)" if up else "rgba(163,58,42,0.07)"
            fig = go.Figure(go.Scatter(
                x=dates, y=prices, mode="lines",
                line=dict(color=line_c, width=1.5),
                fill="tozeroy", fillcolor=fill_c,
                hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
            ))
            fig.update_layout(
                height=140, margin=dict(l=8, r=8, t=8, b=28),
                showlegend=False, **_PAPER_LAYOUT,
                xaxis=dict(**_PAPER_XAXIS),
                yaxis=dict(**_PAPER_YAXIS, tickprefix="$", tickformat=",.0f"),
            )
            st.plotly_chart(fig, use_container_width=True)
            lo = min(prices)
            hi = max(prices)
            st.markdown(f'<div class="meta" style="margin-top:-16px;margin-bottom:24px;">12-month price · {_px(lo)} low · {_px(hi)} high</div>', unsafe_allow_html=True)

        # Inline risk dashboard — fills the empty left-column space
        st.markdown(
            '<div class="meta" style="margin-bottom:10px;">Financial health</div>'
            '<hr class="hr-dark" style="margin-bottom:12px;">',
            unsafe_allow_html=True,
        )
        metrics = risk.get("metrics", {})
        COLOR_MAP = {
            "green": ("rgba(59,107,59,0.15)",  "var(--moss)"),
            "amber": ("rgba(245,158,11,0.15)", "#F59E0B"),
            "red":   ("rgba(163,58,42,0.15)",  "var(--rust)"),
            "na":    ("var(--rule)",            "var(--ink-3)"),
        }
        score = risk.get("overall_score")
        lbl   = risk.get("overall_label", "")
        if score is not None:
            score_color = "var(--moss)" if score >= 7 else "#F59E0B" if score >= 5 else "var(--rust)"
            st.markdown(f"""
            <div style="display:flex;align-items:baseline;gap:14px;margin-bottom:12px;">
              <span style="font-family:var(--mono);font-size:1.4rem;font-weight:700;color:{score_color};">{score:.0f}/10</span>
              <span style="font-size:0.82rem;color:var(--ink-2);">{lbl}</span>
            </div>
            """, unsafe_allow_html=True)
        rows_html = '<div style="display:flex;flex-direction:column;gap:6px;">'
        for m in metrics.values():
            _, accent = COLOR_MAP.get(m["rating"], ("var(--rule)", "var(--ink-3)"))
            rows_html += (
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:8px 0;border-bottom:1px solid var(--rule);">'
                f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{accent};"></span>'
                f'<span style="font-size:0.82rem;color:var(--ink);">{m["label"].split("  ")[0]}</span>'
                f'</div>'
                f'<span style="font-family:var(--mono);font-size:0.82rem;color:{accent};font-weight:600;">{m["value_str"]}</span>'
                f'</div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)

        # Continue button
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        if st.button("Continue to growth →", use_container_width=False, key="snap_cont"):
            st.session_state.chapter = 2
            st.rerun()

    with right:
        # 4 key numbers
        mcap = mkt.get("market_cap")
        beta = mkt.get("beta")
        fcf  = data["fcf"]
        annual = fcf.get("annual", {})
        years  = sorted(annual.keys())

        # Revenue CAGR from FCF/income data
        rev_data = (fin.get("income_statement") or {}).get("revenue") or {}
        rev_years = sorted(yr for yr, v in rev_data.items() if v is not None)
        rev_cagr  = None
        if len(rev_years) >= 2:
            r0, r1 = rev_data[rev_years[0]], rev_data[rev_years[-1]]
            n = len(rev_years) - 1
            if r0 and r1 and r0 > 0 and n > 0:
                rev_cagr = (r1 / r0) ** (1 / n) - 1

        avg_margin = (data["assum"].get("ebit_margin_avg", {}).get("value"))

        st.markdown("""
        <div class="meta" style="margin-bottom:10px;">Three numbers that set the stakes</div>
        <hr class="hr-dark">
        """, unsafe_allow_html=True)

        def _num_stat(label, value, hint, last=False):
            last_cls = " last" if last else ""
            st.markdown(f"""
            <div class="num-stat{last_cls}">
              <div class="num-stat-lbl">{label}</div>
              <div class="num-stat-val">{value}</div>
              <div class="num-stat-hint">{hint}</div>
            </div>
            """, unsafe_allow_html=True)

        _num_stat("Market Capitalisation", _bil(mcap),
                  "what you'd pay for the whole company today")
        _num_stat("Revenue CAGR",
                  _pct(rev_cagr, 1) if rev_cagr is not None else "—",
                  "how fast the top line has compounded historically")
        _num_stat("Average EBIT Margin",
                  _pct(avg_margin, 1) if avg_margin is not None else "—",
                  "fraction of each dollar of sales that becomes operating profit")
        _num_stat("Beta (β)", f"{beta:.2f}" if beta else "—",
                  "how much it swings relative to the market", last=True)

    _hr()

    # Detailed risk cards + FCF table (collapsible)
    with st.expander("Risk dashboard — full breakdown", expanded=False):
        st.markdown(
            '<p style="font-size:0.82rem;color:var(--ink-2);margin:0 0 0.75rem;line-height:1.6;">'
            'Six financial health checks, rated '
            '<span style="color:var(--moss);font-weight:600;">● Healthy</span> &nbsp;·&nbsp; '
            '<span style="color:#F59E0B;font-weight:600;">● Watch</span> &nbsp;·&nbsp; '
            '<span style="color:var(--rust);font-weight:600;">● Concern</span>.</p>',
            unsafe_allow_html=True,
        )
        cards_html = '<div class="risk-grid">'
        for m in risk.get("metrics", {}).values():
            border_color, accent_color = COLOR_MAP.get(m["rating"], ("var(--rule)", "var(--ink-3)"))
            thresh = _RISK_DESC.get(m["label"], "")
            cards_html += (
                f'<div class="risk-card" style="border-color:{border_color};">'
                f'<div class="risk-card-header">'
                f'<div class="risk-dot" style="background:{accent_color};"></div>'
                f'<div class="risk-name">{m["label"]}</div>'
                f'</div>'
                f'<div class="risk-val" style="color:{accent_color};">{m["value_str"]}</div>'
                f'<div class="risk-note">{m["note"]}</div>'
                f'<div class="risk-thresh">{thresh}</div>'
                f'</div>'
            )
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

    with st.expander("Historical Free Cash Flow", expanded=False):
        _render_fcf_table(data)


# ─── Chapter 2: Growth ───────────────────────────────────────────────────────

def _render_chapter_growth() -> None:
    data   = st.session_state.data
    fin    = data["fin"]
    assum  = data["assum"]
    ticker = st.session_state.ticker

    _chrome(chapter=2, total=4, progress=0.50)

    back_col, _ = st.columns([1, 5])
    with back_col:
        st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
        if st.button("← Back", key="back_2"):
            st.session_state.chapter = 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("""
    <span class="eyebrow" style="margin-bottom:16px;display:block;">Chapter two · Growth</span>
    <div class="display rise" style="max-width:24ch; margin-bottom:16px;">
      Shape the <em>next five years</em>.
    </div>
    <p class="lede rise rise1" style="margin-bottom:36px;">
      Pick the growth rate you believe in, or enter a custom figure.
      The chart shows how revenue compares to analyst expectations.
    </p>
    """, unsafe_allow_html=True)

    # Build options
    options: dict[str, float | None] = {}
    arg = assum.get("analyst_revenue_growth", {})
    v = arg.get("next_year", {}).get("value")
    if v is not None:
        options[f"Analyst estimate — next FY  ({v:.2%})"] = v
    v = arg.get("current_year", {}).get("value")
    if v is not None:
        options[f"Analyst estimate — current FY  ({v:.2%})"] = v
    v = assum.get("revenue_cagr_3yr", {}).get("value")
    if v is not None:
        options[f"Historical 3yr CAGR  ({v:.2%})"] = v
    v = assum.get("revenue_cagr_5yr", {}).get("value")
    if v is not None:
        options[f"Historical 5yr CAGR  ({v:.2%})"] = v
    rev_data = (fin.get("income_statement") or {}).get("revenue") or {}
    ry = sorted(yr for yr, val in rev_data.items() if val is not None)
    if len(ry) >= 2:
        y1, y0 = ry[-1], ry[-2]
        r1, r0 = rev_data[y1], rev_data[y0]
        if r0 and r1 and r0 > 0:
            yoy = (r1 - r0) / r0
            options[f"Recent YoY  FY{y0}→FY{y1}  ({yoy:.2%})"] = yoy
    _CUSTOM = "Custom..."
    options[_CUSTOM] = None

    _has_analyst = any("Analyst" in k for k in options)
    _non_custom  = {k: v for k, v in options.items() if v is not None}
    _all_high    = bool(_non_custom) and all(v > 0.30 for v in _non_custom.values())

    saved_g = st.session_state.get("saved_growth") or 0.065
    # find best default index
    _option_keys = list(options.keys())
    _default_idx = 0
    _custom_default = round(saved_g * 100, 1)
    if not _has_analyst and _all_high:
        _default_idx = _option_keys.index(_CUSTOM)
    else:
        for i, (k, v) in enumerate(options.items()):
            if v is not None and abs(v - saved_g) < 0.001:
                _default_idx = i
                break

    chart_col, ctrl_col = st.columns([1.6, 1], gap="large")

    with ctrl_col:
        if not _has_analyst and _all_high:
            st.warning("Analyst estimates unavailable. All historical rates exceed 30% — enter a custom figure.", icon=None)

        selected = st.radio(
            "Growth rate preset",
            _option_keys,
            index=_default_idx,
            label_visibility="collapsed",
            key=f"{ticker}_growth_radio",
        )
        if selected == _CUSTOM:
            growth_rate = st.number_input(
                "Growth rate (%)", value=_custom_default,
                min_value=-50.0, max_value=100.0, step=0.1, format="%.1f",
                key=f"{ticker}_growth_custom",
            ) / 100
        else:
            growth_rate = options[selected]

        rev_series = [rev_data.get(yr) for yr in ry if rev_data.get(yr) is not None]
        last_rev   = rev_series[-1] if rev_series else 1.0
        cagr_5y    = (last_rev * (1 + growth_rate) ** 5 / last_rev - 1) if last_rev else None
        implied_yr5 = last_rev * (1 + growth_rate) ** 5

        st.markdown(f"""
        <div style="margin-top:20px;">
          <div class="meta" style="margin-bottom:6px;">Implied 5-year CAGR</div>
          <div style="font-family:var(--mono);font-size:3rem;font-weight:500;letter-spacing:-0.025em;color:var(--accent);margin-bottom:6px;">{_pct(growth_rate, 1)}</div>
          <div style="font-family:var(--serif);font-style:italic;font-size:13.5px;color:var(--ink-3);line-height:1.5;">
            Revenue grows from
            <span style="font-style:normal;font-family:var(--mono);">{_bil(last_rev)}</span>
            today to
            <span style="font-style:normal;font-family:var(--mono);">{_bil(implied_yr5)}</span>
            by year five.
          </div>
        </div>
        """, unsafe_allow_html=True)

    with chart_col:
        # Revenue chart
        hist_revs  = [rev_data.get(yr) for yr in ry]
        hist_lbls  = [f"FY{yr}" for yr in ry]
        fc_yrs     = list(range(1, 6))
        fc_revs    = [last_rev * (1 + growth_rate) ** i for i in fc_yrs] if last_rev else []
        last_yr    = int(ry[-1]) if ry else 2025
        fc_lbls    = [f"FY{last_yr + i}" for i in fc_yrs]

        analyst_cagr = (arg.get("next_year", {}).get("value")
                        or arg.get("current_year", {}).get("value"))

        fig = go.Figure()

        # History first — sets categorical x-axis order (FY2023, FY2024, ...)
        fig.add_trace(go.Scatter(
            x=hist_lbls, y=[v / 1e9 if v else None for v in hist_revs],
            mode="lines+markers",
            line=dict(color="#5C6B7D", width=2),
            marker=dict(color="#5C6B7D", size=5),
            name="Historical", showlegend=True,
        ))

        # Analyst band — appended after history so forecast years follow historical years
        if analyst_cagr and last_rev:
            band_lo = [last_rev * (1 + max(0, analyst_cagr - 0.03)) ** i / 1e9 for i in fc_yrs]
            band_hi = [last_rev * (1 + analyst_cagr + 0.03) ** i / 1e9 for i in fc_yrs]
            fig.add_trace(go.Scatter(
                x=fc_lbls + fc_lbls[::-1],
                y=band_hi + band_lo[::-1],
                fill="toself", fillcolor="rgba(33,64,199,0.07)",
                line=dict(width=0), showlegend=False,
                hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=fc_lbls, y=[last_rev * (1 + analyst_cagr) ** i / 1e9 for i in fc_yrs],
                mode="lines", line=dict(color="rgba(33,64,199,0.45)", width=1.2, dash="dot"),
                name="Analyst consensus", showlegend=True,
            ))

        # Forecast — connects from last historical point into future years
        all_fc_x = hist_lbls[-1:] + fc_lbls
        all_fc_y = ([hist_revs[-1] / 1e9 if hist_revs else None]
                    + [v / 1e9 for v in fc_revs])
        fig.add_trace(go.Scatter(
            x=all_fc_x, y=all_fc_y,
            mode="lines+markers",
            line=dict(color="#2140C7", width=2.5),
            marker=dict(color="#2140C7", size=7, symbol="circle"),
            name="Your forecast", showlegend=True,
        ))

        fig.update_layout(
            height=300, margin=dict(l=50, r=20, t=32, b=40),
            **_PAPER_LAYOUT,
            xaxis=dict(**_PAPER_XAXIS),
            yaxis=dict(**_PAPER_YAXIS, ticksuffix="B", tickprefix="$"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                        font=dict(size=10, color="#5C6B7D"), bgcolor="rgba(0,0,0,0)"),
            shapes=[dict(
                type="line", xref="x", yref="paper",
                x0=hist_lbls[-1], x1=hist_lbls[-1], y0=0, y1=1,
                line=dict(color="#0B1A2B", width=1, dash="dot"),
            )] if hist_lbls else [],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    if st.button("Continue to profitability →", key="growth_cont"):
        st.session_state.saved_growth = growth_rate
        st.session_state.chapter = 3
        st.rerun()


# ─── Chapter 3: Profitability ─────────────────────────────────────────────────

def _render_chapter_margin() -> None:
    data   = st.session_state.data
    assum  = data["assum"]
    fin    = data["fin"]
    ticker = st.session_state.ticker

    _chrome(chapter=3, total=4, progress=0.75)

    back_col, _ = st.columns([1, 5])
    with back_col:
        st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
        if st.button("← Back", key="back_3"):
            st.session_state.chapter = 2
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("""
    <span class="eyebrow" style="margin-bottom:16px;display:block;">Chapter three · Profitability &amp; cost of capital</span>
    <div class="display rise" style="max-width:28ch; margin-bottom:16px;">
      Where do <em>margins</em> settle?
    </div>
    <p class="lede rise rise1" style="margin-bottom:32px;">
      Set the steady-state EBIT margin and discount rate. These two inputs drive most of the valuation.
    </p>
    """, unsafe_allow_html=True)

    saved_margin = st.session_state.get("saved_margin") or 0.20
    base_margin  = (assum.get("ebit_margin_avg", {}).get("value") or saved_margin)

    # Historical margin bars
    hist_margins: dict = {}
    try:
        income = fin.get("income_statement") or {}
        rev    = income.get("revenue") or {}
        ebit   = income.get("ebit") or {}
        for yr in sorted(rev.keys()):
            r, e = rev.get(yr), ebit.get(yr)
            if r and e and r > 0:
                hist_margins[yr] = e / r
    except Exception:
        pass

    _sec("EBIT Margin")

    margin_col, commentary_col = st.columns([1.5, 1], gap="large")

    with margin_col:
        ebit_margin_pct = st.slider(
            "EBIT Margin", 0.0, 60.0,
            round(base_margin * 100, 1), 0.1, format="%.1f%%",
            help=f"Historical average: {_pct(base_margin)}.",
            key=f"{ticker}_ebit_slider",
        )
        ebit_margin = ebit_margin_pct / 100

        # Peer benchmark — Plotly scatter (replaces fragile absolute-positioned HTML)
        industry_median = base_margin * 0.85
        best_in_class   = base_margin * 1.25

        bm_peers  = [industry_median, base_margin, best_in_class]
        bm_labels = ["Industry median", f"{ticker} 5-yr avg", "Best-in-class"]

        fig_bm = go.Figure()
        x_max = max(best_in_class * 1.15, ebit_margin * 1.05, 0.6)
        x_max = min(x_max, 0.65)
        fig_bm.add_trace(go.Scatter(
            x=bm_peers, y=[0] * len(bm_peers),
            mode="markers+text",
            marker=dict(symbol="line-ns", size=18, color="#5C6B7D",
                        line=dict(color="#5C6B7D", width=2)),
            text=bm_labels,
            textposition="top center",
            textfont=dict(size=9, color="#5C6B7D", family="IBM Plex Mono"),
            hovertemplate="%{text}: %{x:.1%}<extra></extra>",
            showlegend=False,
        ))
        fig_bm.add_trace(go.Scatter(
            x=[ebit_margin], y=[0],
            mode="markers+text",
            marker=dict(symbol="triangle-down", size=14, color="#2140C7"),
            text=[f"{ebit_margin:.1%}"],
            textposition="bottom center",
            textfont=dict(size=11, color="#2140C7", family="IBM Plex Mono"),
            hovertemplate="Your assumption: %{x:.1%}<extra></extra>",
            showlegend=False,
        ))
        fig_bm.update_layout(
            height=90, margin=dict(l=8, r=8, t=28, b=8),
            **_PAPER_LAYOUT,
            xaxis=dict(
                range=[0, x_max],
                tickformat=".0%",
                showgrid=False, zeroline=False,
                tickfont=dict(size=9, color="#5C6B7D", family="IBM Plex Mono"),
            ),
            yaxis=dict(visible=False, range=[-1, 1]),
        )
        st.plotly_chart(fig_bm, use_container_width=True)

        # Historical margin mini bar chart
        if hist_margins:
            yrs_m  = sorted(hist_margins.keys())[-5:]
            vals_m = [hist_margins[y] for y in yrs_m]
            fig_m  = go.Figure(go.Bar(
                x=[f"FY{y}" for y in yrs_m],
                y=[v * 100 for v in vals_m],
                marker_color="#0B1A2B",
                text=[f"{v:.0%}" for v in vals_m],
                textposition="outside",
                textfont=dict(size=10, color="#5C6B7D", family="IBM Plex Mono"),
                hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
            ))
            fig_m.update_layout(
                height=160, margin=dict(l=8, r=8, t=28, b=28),
                **_PAPER_LAYOUT,
                xaxis=dict(**_PAPER_XAXIS),
                yaxis=dict(**_PAPER_YAXIS, ticksuffix="%"),
                title=dict(text="Historical EBIT margin", font=dict(size=11, color="#5C6B7D")),
            )
            st.plotly_chart(fig_m, use_container_width=True)

    with commentary_col:
        if ebit_margin > base_margin * 1.1:
            commentary = (
                f"You're assuming margins expand meaningfully above {ticker}'s average. "
                "That's a real thesis — the business gets more efficient or gains pricing power."
            )
        elif ebit_margin < base_margin * 0.9:
            commentary = (
                "You're assuming margins compress below the historical average. "
                "Competition, cost pressure, or a mix shift toward lower-margin products."
            )
        else:
            commentary = (
                f"You're holding margins roughly in line with the {ticker} historical average. "
                "Steady state — no heroics either direction."
            )

        st.markdown(f"""
        <div style="margin-top:60px;">
          <p style="font-family:var(--serif);font-style:italic;font-size:17px;line-height:1.5;color:var(--ink-2);">
            {commentary}
          </p>
        </div>
        """, unsafe_allow_html=True)

    _hr()

    # Terminal growth rate
    _sec("Terminal Growth Rate")
    st.caption("The assumed growth rate after year 5, in perpetuity. Should not exceed long-run GDP growth (2–3%).")
    tgr_pct = st.slider(
        "Terminal Growth Rate", 0.5, 5.0,
        round(st.session_state.get("saved_tgr", 0.025) * 100, 1),
        0.1, format="%.1f%%",
        key=f"{ticker}_tgr_slider",
    )

    _hr()

    # WACC
    _sec("Cost of Capital (WACC)")
    st.caption(
        "Two forces. How expensive is money right now (risk-free rate) and how risky is this specific business (beta)."
    )

    mkt = data["fin"].get("market_data", {})

    rfr_def  = st.session_state.get("saved_rfr",  0.0425) * 100
    erp_def  = st.session_state.get("saved_erp",  0.045)  * 100
    beta_def = st.session_state.get("saved_beta") or mkt.get("beta") or 1.0
    kd_def   = st.session_state.get("saved_kd",   0.04)   * 100
    tc_def   = st.session_state.get("saved_tc",   0.21)   * 100
    eqw_def  = st.session_state.get("saved_eqw",  0.90)   * 100
    dew_def  = st.session_state.get("saved_dew",  0.10)   * 100

    wacc_col, preview_col = st.columns([1.4, 1], gap="large")

    with wacc_col:
        c1, c2, c3 = st.columns(3)
        with c1:
            rfr  = st.number_input("Risk-free Rate (%)",     value=rfr_def,  step=0.05, format="%.2f", key=f"{ticker}_rfr",
                                   help="10-year US Treasury yield.")
            erp  = st.number_input("Equity Risk Premium (%)", value=erp_def, step=0.05, format="%.2f", key=f"{ticker}_erp",
                                   help="Extra return demanded for owning stocks vs bonds. Typically 4–6%.")
            beta = st.number_input("Beta",                    value=float(beta_def), step=0.01, format="%.2f", key=f"{ticker}_beta",
                                   help="Stock volatility relative to the market.")
        with c2:
            kd   = st.number_input("Cost of Debt (%)",  value=kd_def,  step=0.05, format="%.2f", key=f"{ticker}_kd",
                                   help="Average interest rate on debt.")
            tc   = st.number_input("Tax Rate (%)",       value=tc_def,  step=0.10, format="%.1f", key=f"{ticker}_tc",
                                   help="Effective corporate tax rate.")
        with c3:
            eq_w = st.number_input("Equity Weight (%)", value=eqw_def, step=0.50, format="%.1f", key=f"{ticker}_eqw",
                                   help="Equity as % of total capital.")
            de_w = st.number_input("Debt Weight (%)",   value=dew_def, step=0.50, format="%.1f", key=f"{ticker}_dew",
                                   help="Debt as % of total capital.")

    with preview_col:
        ke_prev  = (rfr / 100) + beta * (erp / 100)
        kd_at    = (kd  / 100) * (1 - tc / 100)
        wacc_pre = ke_prev * (eq_w / 100) + kd_at * (de_w / 100)

        wsum = eq_w + de_w
        if abs(wsum - 100.0) > 0.1:
            st.warning(f"Weights sum to {wsum:.1f}% (should be 100%). Current: {wsum:.1f}%")

        st.markdown(f"""
        <div class="wacc-box" style="margin-top:36px;">
          <div>
            <div class="meta" style="margin-bottom:4px;">Resulting WACC</div>
            <div class="wacc-val">{wacc_pre:.2%}</div>
          </div>
          <div class="wacc-detail">
            Ke = {rfr:.2f}% + {beta:.2f} × {erp:.2f}%
            = <span style="color:var(--ink);font-family:var(--mono);">{ke_prev:.2%}</span><br>
            Kd(AT) = <span style="color:var(--ink);font-family:var(--mono);">{kd_at:.2%}</span>
            &nbsp;·&nbsp;
            WACC = <span style="color:var(--accent);font-family:var(--mono);font-weight:600;">{wacc_pre:.2%}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    if st.button("Reveal the verdict →", key="margin_cont"):
        st.session_state.saved_margin = ebit_margin_pct / 100
        st.session_state.saved_tgr    = tgr_pct / 100
        st.session_state.saved_rfr    = rfr / 100
        st.session_state.saved_erp    = erp / 100
        st.session_state.saved_beta   = beta
        st.session_state.saved_kd     = kd / 100
        st.session_state.saved_tc     = tc / 100
        st.session_state.saved_eqw    = eq_w / 100
        st.session_state.saved_dew    = de_w / 100

        # Run DCF
        user_vals = dict(
            growth_rate = st.session_state.saved_growth or 0.065,
            ebit_margin = st.session_state.saved_margin,
            tgr         = st.session_state.saved_tgr,
            rfr         = st.session_state.saved_rfr,
            erp         = st.session_state.saved_erp,
            beta        = st.session_state.saved_beta,
            kd          = st.session_state.saved_kd,
            tc          = st.session_state.saved_tc,
            eq_w        = st.session_state.saved_eqw,
            de_w        = st.session_state.saved_dew,
        )
        assum_mod, fin_mod = _apply_overrides(data, user_vals)
        with st.spinner("Running DCF model…"):
            dcf = run_dcf(
                ticker_symbol=st.session_state.ticker, assumptions=assum_mod,
                fcf_result=data["fcf"], financial_data=fin_mod,
                revenue_growth_rate=user_vals["growth_rate"],
                terminal_growth_rate=user_vals["tgr"],
                ebit_margin_override=user_vals["ebit_margin"],
            )
        with st.spinner("Computing sensitivity grids…"):
            sens = build_sensitivity(
                ticker_symbol=st.session_state.ticker, base_dcf=dcf,
                assumptions=assum_mod, fcf_result=data["fcf"],
                financial_data=fin_mod,
            )
        st.session_state.update(dcf=dcf, sens=sens, chapter=4)
        st.rerun()


# ─── Apply user overrides ─────────────────────────────────────────────────────

def _apply_overrides(data: dict, user: dict) -> tuple[dict, dict]:
    assum_mod = copy.deepcopy(data["assum"])
    fin_mod   = copy.deepcopy(data["fin"])

    assum_mod["risk_free_rate"]["value"]      = user["rfr"]
    assum_mod["equity_risk_premium"]["value"] = user["erp"]
    assum_mod["cost_of_debt"]["value"]        = user["kd"]
    assum_mod["effective_tax_rate"]["value"]  = user["tc"]
    cs = assum_mod.get("capital_structure")
    if isinstance(cs, dict):
        cs["equity_weight"] = user["eq_w"]
        cs["debt_weight"]   = user["de_w"]

    fin_mod["market_data"]["beta"] = user["beta"]
    return assum_mod, fin_mod


# ─── Chapter 4: Result (Verdict) ─────────────────────────────────────────────

def _render_chapter_result() -> None:
    dcf    = st.session_state.dcf
    sens   = st.session_state.sens
    data   = st.session_state.data
    ticker = st.session_state.ticker

    _chrome(chapter="✓", total=4, progress=1.0)

    back_col, _ = st.columns([1, 5])
    with back_col:
        st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
        if st.button("← Revise", key="back_4"):
            st.session_state.chapter = 3
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    ud  = dcf.get("upside_downside")
    imp = dcf.get("implied_share_price")
    cur = dcf.get("current_price")
    inp = dcf.get("inputs", {})
    wb  = dcf.get("wacc_buildup", {})

    # Verdict headline
    if ud is not None:
        verdict = "undervalued" if ud > 0.05 else "overvalued" if ud < -0.05 else "fairly valued"
        v_color = "var(--moss)" if ud > 0.05 else "var(--rust)" if ud < -0.05 else "var(--ink)"
        ci = data["company_info"]
        st.markdown(f"""
        <span class="eyebrow" style="margin-bottom:16px;display:block;">The verdict · {ticker} · {ci.get('name','')}</span>
        <div class="display-hero rise" style="max-width:22ch; margin-bottom:40px;">
          The stock appears <em style="color:{v_color};">{verdict}</em>.
        </div>
        """, unsafe_allow_html=True)

    # 3-scenario cards
    if imp is not None and cur is not None:
        bear = imp * 0.72
        bull = imp * 1.45

        def _delta_html(v, ref):
            d = (v / ref - 1)
            color = "var(--moss)" if d > 0 else "var(--rust)"
            return f'<span style="color:{color};">{d:+.1%} vs today</span>'

        st.markdown(f"""
        <div class="scenario-grid rise rise1">
          <div class="scenario-card">
            <div class="scenario-lbl" style="color:var(--rust);">Bear case</div>
            <div class="scenario-val">{_px(bear)}</div>
            <div class="scenario-delta">{_delta_html(bear, cur)}</div>
            <div class="scenario-note">Margins compress, growth disappoints</div>
          </div>
          <div class="scenario-card base">
            <div class="scenario-lbl" style="color:var(--ink);">Base case</div>
            <div class="scenario-val">{_px(imp)}</div>
            <div class="scenario-delta">{_delta_html(imp, cur)}</div>
            <div class="scenario-note">Your assumptions play out as set</div>
          </div>
          <div class="scenario-card">
            <div class="scenario-lbl" style="color:var(--gold);">Bull case</div>
            <div class="scenario-val">{_px(bull)}</div>
            <div class="scenario-delta">{_delta_html(bull, cur)}</div>
            <div class="scenario-note">Operating leverage + multiple expansion</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Thesis + model summary
    cagr  = inp.get("revenue_growth_rate", 0)
    ebit  = inp.get("ebit_margin", 0)
    wacc  = wb.get("wacc", 0)
    tgr   = inp.get("terminal_growth_rate", 0)

    thesis_col, model_col = st.columns([1.2, 1], gap="large")

    with thesis_col:
        if ud is not None and imp is not None:
            direction = "undervalued" if ud >= 0 else "overvalued"
            col_dir   = "var(--moss)" if ud >= 0 else "var(--rust)"
            st.markdown(f"""
            <div style="margin-bottom:24px;">
              <div class="meta" style="margin-bottom:10px;">Your thesis, in one sentence</div>
              <p style="font-family:var(--serif);font-style:italic;font-size:1.15rem;color:var(--ink);line-height:1.55;max-width:50ch;">
                Revenue compounds at
                <b style="font-style:normal;color:var(--accent);font-family:var(--mono);">{_pct(cagr, 1)}</b>,
                margins settle at
                <b style="font-style:normal;color:var(--accent);font-family:var(--mono);">{_pct(ebit, 1)}</b>,
                discounted back at
                <b style="font-style:normal;color:var(--accent);font-family:var(--mono);">{_pct(wacc, 2)}</b>
                — yielding a fair value of
                <b style="font-style:normal;font-family:var(--mono);">{_px(imp)}</b>
                against today's
                <b style="font-style:normal;font-family:var(--mono);">{_px(cur)}</b>.
              </p>
            </div>
            """, unsafe_allow_html=True)

        # Narrative
        if ud is not None:
            col_dir = "var(--moss)" if ud >= 0 else "var(--rust)"
            pv_tv   = dcf.get("pv_terminal_value")
            ev      = dcf.get("enterprise_value")
            tv_pct  = (pv_tv / ev * 100) if (pv_tv and ev) else None
            tv_note = f" — {tv_pct:.0f}% of EV from terminal value" if tv_pct else ""
            direction = "undervalued" if ud >= 0 else "overvalued"
            st.markdown(f"""
            <div class="narrative">
              <strong>Model summary:</strong>
              At a WACC of <span style="color:var(--accent);font-family:var(--mono);">{_pct(wacc)}</span>,
              with revenue growing at <span style="color:var(--accent);font-family:var(--mono);">{_pct(cagr)}</span>
              and EBIT margins of <span style="color:var(--accent);font-family:var(--mono);">{_pct(ebit)}</span>,
              the stock appears <span style="color:{col_dir};font-weight:600;">{direction}</span>
              versus its current price of {_px(cur)}.
              Terminal growth: <span style="color:var(--accent);font-family:var(--mono);">{_pct(tgr)}</span>{tv_note}.
            </div>
            """, unsafe_allow_html=True)

    with model_col:
        bridge = dcf.get("bridge", {})
        ev_val = dcf.get("enterprise_value")
        pv_sum = dcf.get("pv_fcf_sum")
        shs    = bridge.get("shares_outstanding")
        shs_s  = f"{shs/1e9:.2f}B" if shs else "—"
        imp_cls = "pos" if (ud or 0) >= 0 else "neg"

        st.markdown("""
        <div class="meta" style="margin-bottom:10px;">The model at a glance</div>
        <hr class="hr-dark">
        """, unsafe_allow_html=True)

        rows_md = [
            ("Revenue CAGR", _pct(cagr, 1), False),
            ("EBIT margin",  _pct(ebit, 1), False),
            ("WACC",         _pct(wacc, 2), False),
            ("Terminal growth", _pct(tgr, 1), False),
            ("Enterprise value", _bil(ev_val), False),
            ("Equity value", _bil(bridge.get("equity_value")), True),
            ("Fair value / share", _px(imp), True),
        ]
        for i, (lbl, val, is_acc) in enumerate(rows_md):
            last_cls = " last" if i == len(rows_md) - 1 else ""
            val_cls  = " acc" if is_acc else ""
            st.markdown(f"""
            <div class="model-row{last_cls}">
              <span class="model-row-lbl">{lbl}</span>
              <span class="model-row-val{val_cls} num">{val}</span>
            </div>
            """, unsafe_allow_html=True)

    _hr()

    # Detailed tables (collapsible)
    with st.expander("WACC Build-Up & Equity Bridge", expanded=False):
        col_wacc, col_bridge = st.columns(2)
        with col_wacc:
            _sec("WACC Build-Up")
            _htable(
                ["Component", "Value"],
                [
                    ["Risk-free Rate",          _pct(wb.get("risk_free_rate"))],
                    ["Beta",                    _x(  wb.get("beta"))],
                    ["Equity Risk Premium",     _pct(wb.get("equity_risk_premium"))],
                    ["Cost of Equity (CAPM)",   _pct(wb.get("cost_of_equity"))],
                    ["Cost of Debt (pre-tax)",  _pct(wb.get("cost_of_debt_pretax"))],
                    ["After-tax Cost of Debt",  _pct(wb.get("after_tax_cost_of_debt"))],
                    ["Equity Weight",           _pct(wb.get("equity_weight"))],
                    ["Debt Weight",             _pct(wb.get("debt_weight"))],
                    ["WACC",                    _pct(wb.get("wacc"))],
                ],
                highlight_last=True,
            )
        with col_bridge:
            _sec("Equity Bridge")
            pv_tv  = dcf.get("pv_terminal_value")
            ev     = dcf.get("enterprise_value")
            tv_pct = (pv_tv / ev * 100) if (pv_tv and ev) else None
            tv_s   = _bil(pv_tv) + (f'  <span class="muted">({tv_pct:.0f}% of EV)</span>' if tv_pct else "")
            imp_s  = f'<span class="{"pos" if (ud or 0) >= 0 else "neg"}">{_px(imp)}</span>'
            _htable(
                ["Item", "Value"],
                [
                    ["PV of FCFs",           _bil(pv_sum)],
                    ["PV of Terminal Value", tv_s],
                    ["Enterprise Value",     _bil(ev)],
                    ["(−) Total Debt",       _bil(bridge.get("total_debt"))],
                    ["(+) Cash",             _bil(bridge.get("cash_and_equivalents"))],
                    ["Equity Value",         _bil(bridge.get("equity_value"))],
                    ["Shares Outstanding",   shs_s],
                    ["Implied Price",        imp_s],
                    ["Current Price",        _px(cur)],
                ],
            )

    with st.expander("5-Year FCF Projection", expanded=False):
        _render_fcf_projection(dcf)

    if sens:
        with st.expander("Sensitivity Analysis", expanded=True):
            _render_sensitivity(dcf, sens)

    warns = dcf.get("warnings", [])
    if warns:
        with st.expander(f"{len(warns)} valuation warning(s)", expanded=False):
            for w in warns:
                st.warning(w)

    # Restart button
    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    _, btn_col, _ = st.columns([1, 1.5, 1])
    with btn_col:
        st.markdown('<div class="ghost-btn">', unsafe_allow_html=True)
        if st.button("Start a new analysis →", use_container_width=True, key="restart"):
            st.session_state.update(
                chapter=0, ticker="", data=None, dcf=None, sens=None,
                saved_growth=None, saved_margin=None,
            )
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ─── FCF table (shared) ───────────────────────────────────────────────────────

def _render_fcf_table(data: dict) -> None:
    fcf    = data["fcf"]
    annual = fcf.get("annual", {})
    years  = sorted(annual.keys())

    if not years:
        st.info("No FCF data available.")
        return

    headers = [""] + [f"FY{yr}" for yr in years]
    rows_def = [
        ("EBIT",         "ebit",           False),
        ("D&A",          "da",             False),
        ("Operating CF", "opcf",           False),
        ("ΔNWC",         "delta_nwc",      False),
        ("CapEx",        "capex",          False),
        ("FCF",          "fcf",            False),
        ("FCF / EBIT",   "fcf_ebit_ratio", True),
    ]

    uses_direct   = any(annual.get(yr, {}).get("fcf_method") == "direct"   for yr in years)
    uses_reported = any(annual.get(yr, {}).get("fcf_method") == "reported" for yr in years)

    rows = []
    for label, key, is_ratio in rows_def:
        row = [label]
        for yr in years:
            yr_data = annual.get(yr, {})
            v       = yr_data.get(key)
            method  = yr_data.get("fcf_method")
            if v is None:
                row.append('<span class="muted">—</span>')
            elif is_ratio:
                sup = " †" if method in ("direct", "reported") else ""
                row.append(f'<span class="num">{v:.2f}×{sup}</span>')
            else:
                cls = _val_cls(v) if key == "fcf" else ""
                sup = " †" if key == "fcf" and method in ("direct", "reported") else ""
                txt = f"{_bil(v)}{sup}"
                row.append(f'<span class="num {cls}">{txt}</span>' if cls else f'<span class="num">{txt}</span>')
        rows.append(row)

    col_tbl, col_meta = st.columns([3, 1])
    with col_tbl:
        _htable(headers, rows)
        if uses_direct or uses_reported:
            st.caption("† FCF = Operating CF − CapEx (ΔNWC-based formula unavailable)")
    with col_meta:
        tc   = fcf.get("effective_tax_rate")
        avg3 = fcf.get("fcf_ebit_3yr_avg")
        avg5 = fcf.get("fcf_ebit_5yr_avg")
        html = '<div class="kpi-row" style="flex-direction:column;gap:8px;">'
        if tc   is not None: html += _kpi("Effective Tax Rate", _pct(tc))
        if avg3 is not None: html += _kpi("FCF/EBIT  3yr avg",  _x(avg3))
        if avg5 is not None: html += _kpi("FCF/EBIT  5yr avg",  _x(avg5))
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    if fcf.get("fcf_ebit_volatility_flag"):
        st.warning("High FCF/EBIT volatility — forecast sensitivity will be wider.")


# ─── FCF projection (result) ─────────────────────────────────────────────────

def _render_fcf_projection(dcf: dict) -> None:
    proj    = dcf.get("projection", {})
    inp     = dcf.get("inputs", {})
    base_yr = dcf.get("base_year")
    base_rv = dcf.get("base_revenue")
    years   = sorted(proj.keys())

    if not years:
        st.info("No projection data.")
        return

    st.caption(
        f"Rev. growth {_pct(inp.get('revenue_growth_rate'))}  ·  "
        f"EBIT margin {_pct(inp.get('ebit_margin'))}  ·  "
        f"FCF/EBIT {_x(inp.get('fcf_ebit_ratio'))}  ·  "
        f"Terminal growth {_pct(inp.get('terminal_growth_rate'))}"
    )
    hdrs = [""] + [f"FY{base_yr} (Base)"] + [f"FY{yr}" for yr in years]
    rows = [
        ["Revenue"]         + [_bil(base_rv)] + [_bil(proj[y].get("revenue"))        for y in years],
        ["EBIT"]            + ["—"]            + [_bil(proj[y].get("ebit"))           for y in years],
        ["FCF"]             + ["—"]            + [_bil(proj[y].get("fcf"))            for y in years],
        ["Discount Factor"] + ["—"]            + [f"{proj[y].get('discount_factor',0):.4f}" for y in years],
        ["PV of FCF"]       + ["—"]            + [_bil(proj[y].get("pv_fcf"))         for y in years],
    ]
    _htable(hdrs, rows)

    yr_lbls  = [f"FY{yr}" for yr in years]
    fcf_vals = [proj[y].get("fcf") for y in years]
    pv_vals  = [proj[y].get("pv_fcf") for y in years]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Projected FCF", x=yr_lbls,
        y=[v / 1e9 if v else None for v in fcf_vals],
        marker_color="#2140C7",
        hovertemplate="<b>%{x}</b><br>FCF: $%{y:.2f}B<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="PV of FCF", x=yr_lbls,
        y=[v / 1e9 if v else None for v in pv_vals],
        marker_color="rgba(33,64,199,0.30)",
        marker_line=dict(color="#2140C7", width=1),
        hovertemplate="<b>%{x}</b><br>PV: $%{y:.2f}B<extra></extra>",
    ))
    fig.update_layout(
        barmode="group", height=220,
        margin=dict(l=60, r=20, t=24, b=28),
        **_PAPER_LAYOUT,
        xaxis=dict(**_PAPER_XAXIS),
        yaxis=dict(**_PAPER_YAXIS, tickprefix="$", ticksuffix="B"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(size=10, color="#5C6B7D"), bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ─── Sensitivity heatmap ──────────────────────────────────────────────────────

def _render_sensitivity(dcf: dict, sens: dict) -> None:
    st.caption("Each cell shows implied upside/downside when two assumptions shift simultaneously. Blue-outlined cell = your base case.")
    tab1, tab2 = st.tabs(["WACC × Terminal Growth Rate", "Revenue Growth × EBIT Margin"])
    with tab1:
        t1 = sens.get("table1")
        if t1:
            _render_heatmap(t1, "WACC", "Terminal Growth Rate")
    with tab2:
        t2 = sens.get("table2")
        if t2:
            _render_heatmap(t2, "Revenue Growth", "EBIT Margin")


def _render_heatmap(table: dict, row_label: str, col_label: str) -> None:
    row_values = table["row_values"]
    col_values = table["col_values"]
    upsides    = table["upsides"]
    b_row      = table["base_row_idx"]
    b_col      = table["base_col_idx"]
    n_rows     = len(row_values)
    n_cols     = len(col_values)

    z_data, text_data = [], []
    for ri in range(n_rows):
        z_row, t_row = [], []
        for ci in range(n_cols):
            ud = upsides[ri][ci]
            z_row.append(ud * 100 if ud is not None else None)
            t_row.append(f"{ud:+.1%}" if ud is not None else "—")
        z_data.append(z_row)
        text_data.append(t_row)

    z_plot   = z_data[::-1]
    t_plot   = text_data[::-1]
    row_lbls = [f"{v:.2%}" for v in reversed(row_values)]
    col_lbls = [f"{v:.1%}" for v in col_values]
    b_row_inv = n_rows - 1 - b_row

    x_coords = list(range(n_cols))
    y_coords = list(range(n_rows))

    flat = [v for row in z_plot for v in row if v is not None]
    zmax = max((abs(v) for v in flat), default=20)
    zmax = max(zmax, 5)

    custom = [[[ row_lbls[ri], col_lbls[ci]] for ci in range(n_cols)] for ri in range(n_rows)]

    fig = go.Figure(go.Heatmap(
        z=z_plot, x=x_coords, y=y_coords,
        text=t_plot, texttemplate="%{text}",
        textfont=dict(size=11, family="'IBM Plex Mono', monospace", color="#0B1A2B"),
        customdata=custom,
        colorscale=[
            [0.00, "#A33A2A"],
            [0.45, "#D4907F"],
            [0.50, "#F5F1E8"],
            [0.55, "#8FAD8F"],
            [1.00, "#3B6B3B"],
        ],
        zmin=-zmax, zmid=0, zmax=zmax,
        colorbar=dict(
            title=dict(text="Upside %", font=dict(family="Inter", size=11, color="#5C6B7D")),
            tickformat=".0f", ticksuffix="%",
            tickfont=dict(family="Inter", size=10, color="#5C6B7D"),
            tickcolor="#D9D1BD",
            bgcolor="#F5F1E8", bordercolor="#D9D1BD",
            thickness=12, len=0.85,
        ),
        hovertemplate=(
            f"<b>{row_label}</b>: %{{customdata[0]}}<br>"
            f"<b>{col_label}</b>: %{{customdata[1]}}<br>"
            "<b>Upside</b>: %{text}<extra></extra>"
        ),
    ))

    fig.add_shape(
        type="rect", xref="x", yref="y",
        x0=b_col - 0.5, x1=b_col + 0.5,
        y0=b_row_inv - 0.5, y1=b_row_inv + 0.5,
        line=dict(color="#2140C7", width=2.5),
        fillcolor="rgba(33,64,199,0.08)",
    )

    fig.update_layout(
        xaxis=dict(
            title=dict(text=col_label, font=dict(size=11, color="#5C6B7D")),
            tickmode="array", tickvals=x_coords, ticktext=col_lbls,
            showgrid=False, zeroline=False,
            tickfont=dict(color="#5C6B7D", size=10), color="#5C6B7D",
        ),
        yaxis=dict(
            title=dict(text=row_label, font=dict(size=11, color="#5C6B7D")),
            tickmode="array", tickvals=y_coords, ticktext=row_lbls,
            showgrid=False, zeroline=False,
            tickfont=dict(color="#5C6B7D", size=10), color="#5C6B7D",
        ),
        height=400, margin=dict(l=80, r=80, t=16, b=60),
        font=dict(family="Inter, sans-serif", size=11, color="#0B1A2B"),
        plot_bgcolor="#EDE7D6",
        paper_bgcolor="#F5F1E8",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Blue outline = base case assumptions")

    flat_upsides = [
        upsides[ri][ci]
        for ri in range(n_rows) for ci in range(n_cols)
        if upsides[ri][ci] is not None
    ]
    if flat_upsides:
        bear_val = min(flat_upsides)
        bull_val = max(flat_upsides)
        base_val = upsides[b_row][b_col]
        bear_color = "var(--rust)"  if bear_val < 0 else "var(--moss)"
        bull_color = "var(--moss)"  if bull_val > 0 else "var(--rust)"
        st.markdown(f"""
        <div style="display:flex;justify-content:center;gap:8px;margin-top:6px;margin-bottom:4px;">
          <div style="text-align:center;background:white;border:1px solid rgba(163,58,42,0.3);
                      padding:8px 20px;min-width:110px;">
            <div class="meta" style="margin-bottom:4px;">Bear Case</div>
            <div style="font-family:var(--mono);font-size:1rem;font-weight:700;color:{bear_color};">{bear_val:+.1%}</div>
          </div>
          <div style="text-align:center;background:var(--paper-2);border:1px solid rgba(33,64,199,0.3);
                      padding:8px 20px;min-width:110px;">
            <div class="meta" style="margin-bottom:4px;">Base Case</div>
            <div style="font-family:var(--mono);font-size:1rem;font-weight:700;color:var(--accent);">{base_val:+.1%}</div>
          </div>
          <div style="text-align:center;background:white;border:1px solid rgba(59,107,59,0.3);
                      padding:8px 20px;min-width:110px;">
            <div class="meta" style="margin-bottom:4px;">Bull Case</div>
            <div style="font-family:var(--mono);font-size:1rem;font-weight:700;color:{bull_color};">{bull_val:+.1%}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()
    st.markdown(_CSS, unsafe_allow_html=True)

    chapter = st.session_state.chapter

    if chapter == 0:
        _render_landing()
    elif chapter == 1:
        _render_chapter_snapshot()
    elif chapter == 2:
        _render_chapter_growth()
    elif chapter == 3:
        _render_chapter_margin()
    elif chapter == 4:
        _render_chapter_result()
    else:
        st.session_state.chapter = 0
        st.rerun()


if __name__ == "__main__":
    main()
