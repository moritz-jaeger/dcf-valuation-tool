"""
app.py
------
Streamlit DCF Valuation Tool — professional finance/tech dark theme.
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
    initial_sidebar_state="expanded",
)


# ─── Design system ────────────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

/* ── Token layer ────────────────────────────────────────── */
:root {
  --bg:          #020617;
  --surface-1:   #0F172A;
  --surface-2:   #1E293B;
  --surface-3:   #334155;
  --border:      #1E293B;
  --border-hi:   #334155;
  --text-1:      #F8FAFC;
  --text-2:      #94A3B8;
  --text-3:      #475569;
  --blue:        #3B82F6;
  --blue-dim:    rgba(59,130,246,0.12);
  --blue-border: rgba(59,130,246,0.30);
  --green:       #22C55E;
  --green-dim:   rgba(34,197,94,0.10);
  --red:         #EF4444;
  --red-dim:     rgba(239,68,68,0.10);
  --amber:       #F59E0B;
  --mono:        'IBM Plex Mono', 'SF Mono', monospace;
}

/* ── Global ─────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {
  background: #020617 !important;
  color: #F8FAFC !important;
}
html, body, input, button, textarea, select,
.stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown div,
[data-testid="stSidebar"], [data-testid="stSidebar"] * {
  font-family: 'Inter', -apple-system, sans-serif !important;
}
/* Force text visibility against dark background */
.stMarkdown, .stMarkdown p, .stMarkdown li,
[data-testid="stText"], [data-testid="stCaption"] p,
[data-testid="stCaptionContainer"] p {
  color: #94A3B8 !important;
}
.main .block-container { padding: 1.5rem 2.5rem 4rem; max-width: 1280px; }

/* ── Hide Streamlit chrome ──────────────────────────────── */
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar ────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: #0F172A !important;
  border-right: 1px solid #1E293B !important;
}
[data-testid="stSidebar"] .stButton > button {
  background: transparent !important;
  color: var(--text-2) !important;
  border: 1px solid var(--border-hi) !important;
  border-radius: 6px !important;
  font-size: 0.82rem !important;
  font-weight: 500 !important;
  transition: all 0.18s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  border-color: var(--blue) !important;
  color: var(--text-1) !important;
}

/* ── Buttons ────────────────────────────────────────────── */
.stButton > button {
  background: var(--blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 7px !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.01em !important;
  transition: background 0.18s, transform 0.12s !important;
  cursor: pointer !important;
}
.stButton > button:hover { background: #2563EB !important; transform: translateY(-1px) !important; }
.stButton > button:active { transform: translateY(0) !important; }

/* ── Sliders ────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] {
  background: var(--blue) !important;
  border: 2px solid var(--blue) !important;
  box-shadow: 0 0 0 3px var(--blue-dim) !important;
}

/* ── Inputs ─────────────────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input {
  color: var(--text-1) !important;
  background: var(--surface-2) !important;
  border: 1px solid var(--border-hi) !important;
  border-radius: 7px !important;
  font-family: var(--mono) !important;
}
[data-testid="stTextInput"] input {
  font-family: 'Inter', sans-serif !important;
  font-size: 1rem !important;
  padding: 0.6rem 1rem !important;
}
[data-testid="stTextInput"] input:focus {
  border-color: var(--blue) !important;
  box-shadow: 0 0 0 3px var(--blue-dim) !important;
}
[data-testid="stRadio"] label { color: var(--text-2) !important; }

/* ── Expanders ──────────────────────────────────────────── */
[data-testid="stExpander"] {
  background: var(--surface-1) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
  color: var(--text-1) !important;
  font-weight: 600 !important;
}

/* ── Tabs ───────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tab"] {
  color: var(--text-2) !important;
  font-size: 0.85rem !important;
  font-weight: 500 !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--text-1) !important;
  font-weight: 600 !important;
  border-bottom-color: var(--blue) !important;
}

/* ── KPI cards ──────────────────────────────────────────── */
.kpi-row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.kpi-card {
  flex: 1; min-width: 140px;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-top: 2px solid var(--blue);
  border-radius: 10px;
  padding: 14px 18px;
  transition: border-color 0.18s;
}
.kpi-card:hover { border-top-color: #60A5FA; }
.kpi-lbl {
  font-size: 0.62rem; font-weight: 600; color: var(--text-3);
  text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 7px;
}
.kpi-val {
  font-size: 1.45rem; font-weight: 700; color: var(--text-1);
  font-family: var(--mono); letter-spacing: -0.02em;
}
.kpi-sub { font-size: 0.7rem; color: var(--text-2); margin-top: 5px; }

/* ── Section headers ────────────────────────────────────── */
.sec-wrap {
  display: flex; align-items: center; gap: 10px;
  margin: 2rem 0 0.9rem;
}
.sec-bar {
  width: 3px; height: 18px; background: var(--blue);
  border-radius: 2px; flex-shrink: 0;
}
.sec {
  font-size: 0.78rem; font-weight: 700; color: var(--text-2);
  text-transform: uppercase; letter-spacing: 0.1em;
}

/* ── Tables ─────────────────────────────────────────────── */
.htable { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
.htable th {
  background: var(--surface-2); color: var(--text-3);
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.09em; padding: 9px 14px; text-align: right;
  border-bottom: 1px solid var(--border);
}
.htable th:first-child { text-align: left; }
.htable td {
  padding: 9px 14px; color: var(--text-1);
  border-bottom: 1px solid var(--border);
  text-align: right;
}
.htable td:first-child {
  text-align: left; color: var(--text-2);
  font-size: 0.82rem;
}
.htable tr:last-child td { border-bottom: none; }
.htable tr:hover td { background: rgba(59,130,246,0.04); }
.num  { font-family: var(--mono); }
.pos  { color: var(--green) !important; }
.neg  { color: var(--red) !important; }
.muted { color: var(--text-3); }
.acc  { color: var(--blue) !important; font-weight: 600; }

/* ── Dividers ───────────────────────────────────────────── */
.hr { border: none; border-top: 1px solid var(--border); margin: 1.75rem 0; }

/* ── Result hero ────────────────────────────────────────── */
.result-hero {
  border-radius: 14px; padding: 2.5rem 2rem;
  text-align: center;
  background: var(--surface-1);
  border: 1px solid var(--border);
  position: relative; overflow: hidden;
}
.result-hero::before {
  content: '';
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 60%; height: 1px;
  background: linear-gradient(90deg, transparent, var(--blue), transparent);
}
.result-price {
  font-size: 4.5rem; font-weight: 700; color: var(--text-1);
  font-family: var(--mono); letter-spacing: -0.04em; line-height: 1.1;
}
.result-lbl {
  font-size: 0.65rem; color: var(--text-3);
  text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.8rem;
  font-weight: 600;
}
.result-cur { font-size: 0.85rem; color: var(--text-2); margin-top: 0.4rem; }
.result-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 0.3rem 0.9rem; border-radius: 6px;
  font-family: var(--mono); font-size: 1.1rem; font-weight: 600;
  margin-top: 0.8rem;
}
.result-badge.pos { background: var(--green-dim); color: var(--green); border: 1px solid rgba(34,197,94,0.25); }
.result-badge.neg { background: var(--red-dim);   color: var(--red);   border: 1px solid rgba(239,68,68,0.25); }

/* ── Landing ────────────────────────────────────────────── */
.landing-wrap {
  min-height: 92vh;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 3rem 1rem 2rem;
}
.hero-badge {
  display: inline-flex; align-items: center; gap: 7px;
  background: var(--blue-dim); border: 1px solid var(--blue-border);
  border-radius: 999px; padding: 5px 14px;
  font-size: 0.68rem; font-weight: 700; color: var(--blue);
  text-transform: uppercase; letter-spacing: 0.12em;
  margin-bottom: 1.6rem;
}
.hero-badge-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--blue);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.5; transform: scale(0.85); }
}
.hero-title {
  font-size: clamp(2.4rem, 5vw, 3.8rem);
  font-weight: 800; color: var(--text-1);
  text-align: center; line-height: 1.12;
  letter-spacing: -0.03em; margin-bottom: 0.7rem;
}
.hero-accent {
  background: linear-gradient(135deg, #3B82F6, #60A5FA);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-sub {
  font-size: 1rem; color: var(--text-2);
  text-align: center; max-width: 460px;
  line-height: 1.65; margin: 0 auto 2.2rem;
}
.hero-stats {
  display: flex; gap: 2rem; justify-content: center;
  flex-wrap: wrap; margin-bottom: 2.5rem;
}
.hero-stat { text-align: center; }
.hero-stat-val {
  font-size: 1.5rem; font-weight: 700; color: var(--text-1);
  font-family: var(--mono); letter-spacing: -0.02em;
}
.hero-stat-lbl {
  font-size: 0.68rem; color: var(--text-3); text-transform: uppercase;
  letter-spacing: 0.09em; margin-top: 2px;
}
.hero-divider {
  width: 1px; height: 36px; background: var(--border);
  align-self: center;
}
.chip {
  display: inline-flex; align-items: center;
  padding: 5px 14px;
  background: var(--surface-2); border: 1px solid var(--border-hi);
  border-radius: 6px; color: var(--text-2);
  font-size: 0.76rem; font-weight: 600;
  cursor: pointer; margin: 0 4px;
  font-family: var(--mono);
  transition: all 0.15s;
}
.chip:hover { border-color: var(--blue); color: var(--text-1); }

/* ── Feature cards ──────────────────────────────────────── */
.feat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 2rem; }
.feat-card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 12px; padding: 22px;
  transition: border-color 0.2s, transform 0.2s;
}
.feat-card:hover { border-color: var(--border-hi); transform: translateY(-2px); }
.feat-icon-wrap {
  width: 40px; height: 40px; border-radius: 9px;
  background: var(--blue-dim); border: 1px solid var(--blue-border);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 14px;
}
.feat-icon-wrap .material-symbols-outlined {
  font-size: 1.25rem; color: var(--blue);
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}
.feat-title { font-size: 0.9rem; font-weight: 700; color: var(--text-1); margin-bottom: 6px; }
.feat-desc  { font-size: 0.79rem; color: var(--text-2); line-height: 1.55; }

/* ── Narrative box ──────────────────────────────────────── */
.narrative {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-left: 3px solid var(--blue);
  border-radius: 10px; padding: 16px 20px;
  margin-bottom: 1.5rem;
  font-size: 0.87rem; color: var(--text-2);
  line-height: 1.7;
}
.narrative strong { color: var(--text-1); }

/* ── WACC preview box ───────────────────────────────────── */
.wacc-box {
  background: var(--surface-2);
  border: 1px solid var(--border-hi);
  border-radius: 10px; padding: 16px 20px;
  margin-top: 12px;
  display: flex; align-items: center; gap: 28px; flex-wrap: wrap;
}
.wacc-val {
  font-family: var(--mono); font-size: 2rem; font-weight: 700; color: var(--blue);
}
.wacc-detail { font-size: 0.8rem; color: var(--text-2); line-height: 1.7; }

/* ── Assumption strip ───────────────────────────────────── */
.assumption-strip {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  background: #1E293B; border: 1px solid #334155;
  border-left: 3px solid #3B82F6; border-radius: 8px;
  padding: 10px 16px; margin-bottom: 12px;
}
.astrip-label { font-size: 0.62rem; font-weight: 700; color: #475569;
                text-transform: uppercase; letter-spacing: 0.09em; margin-right: 4px; }
.astrip-chip  { background: #0F172A; border: 1px solid #334155; border-radius: 5px;
                padding: 3px 10px; font-family: 'IBM Plex Mono',monospace;
                font-size: 0.75rem; font-weight: 600; color: #3B82F6; }
.astrip-sep   { color: #334155; font-size: 0.75rem; }

/* ── Risk cards ─────────────────────────────────────────── */
.risk-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 4px; }
.risk-card { background: #0F172A; border: 1px solid #1E293B; border-radius: 10px; padding: 14px 16px; }
.risk-card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.risk-dot  { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.risk-name { font-size: 0.62rem; font-weight: 700; color: #475569;
             text-transform: uppercase; letter-spacing: 0.09em; }
.risk-val  { font-size: 1.35rem; font-weight: 700; font-family: 'IBM Plex Mono',monospace;
             letter-spacing: -0.02em; margin-bottom: 4px; }
.risk-note { font-size: 0.72rem; color: #94A3B8; line-height: 1.5; margin-bottom: 5px; }
.risk-thresh { font-size: 0.62rem; color: #475569; line-height: 1.4; }

/* ── Animations ─────────────────────────────────────────── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
.au  { animation: fadeInUp 0.5s cubic-bezier(0.22,1,0.36,1) both; }
.au1 { animation: fadeInUp 0.5s cubic-bezier(0.22,1,0.36,1) 0.07s both; }
.au2 { animation: fadeInUp 0.5s cubic-bezier(0.22,1,0.36,1) 0.14s both; }
.au3 { animation: fadeInUp 0.5s cubic-bezier(0.22,1,0.36,1) 0.21s both; }
.au4 { animation: fadeInUp 0.5s cubic-bezier(0.22,1,0.36,1) 0.28s both; }
</style>
"""


# ─── Session state ────────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults: dict[str, Any] = {
        "step":   0,
        "ticker": "",
        "data":   None,
        "dcf":    None,
        "sens":   None,
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


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def _render_sidebar() -> None:
    step   = st.session_state.step
    ticker = st.session_state.ticker

    with st.sidebar:
        if ticker and step > 0 and st.session_state.data:
            ci           = st.session_state.data["company_info"]
            company_name = ci.get("name", ticker)
            sector       = ci.get("sector", "")
            st.markdown(f"""
            <div style="padding: 1.25rem 0.5rem 0.5rem;">
              <div style="font-size:0.6rem;font-weight:700;color:#3B82F6;text-transform:uppercase;
                          letter-spacing:0.1em;margin-bottom:6px;">Active Analysis</div>
              <div style="font-family:'IBM Plex Mono',monospace; font-size:2rem;
                          font-weight:700; color:#F8FAFC; letter-spacing:-0.03em;">{ticker}</div>
              <div style="font-size:0.78rem; color:#94A3B8; margin-top:2px;">{company_name}</div>
              <div style="font-size:0.68rem; color:#475569; margin-top:2px;">{sector}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding: 1.25rem 0.5rem 0.5rem;">
              <div style="font-size:0.6rem;font-weight:700;color:#3B82F6;text-transform:uppercase;
                          letter-spacing:0.12em;margin-bottom:8px;">Valuation Engine</div>
              <div style="font-size:1rem; font-weight:700; color:#F8FAFC;">DCF Analysis</div>
              <div style="font-size:0.75rem; color:#475569; margin-top:3px;">Institutional-grade</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<hr style="border:none;border-top:1px solid #1E293B;margin:0.75rem 0">', unsafe_allow_html=True)

        # ── Stepper ──────────────────────────────────────────────────
        steps = [
            ("Snapshot",    "monitoring"),
            ("Assumptions", "tune"),
            ("Valuation",   "calculate"),
            ("Results",     "insights"),
        ]

        def _step_status(label: str) -> str:
            if step >= 2:
                return "done"
            if step == 1:
                return "done" if label == "Snapshot" else "active" if label == "Assumptions" else "future"
            return "future"

        stepper_html = '<div style="padding: 0 0.25rem; margin-bottom: 1.25rem;">'
        for idx, (label, icon) in enumerate(steps):
            status = _step_status(label)
            if status == "done":
                circle = (
                    '<div style="width:26px;height:26px;border-radius:50%;background:#22C55E;'
                    'display:flex;align-items:center;justify-content:center;font-size:0.7rem;'
                    'font-weight:700;color:#020617;flex-shrink:0;">✓</div>'
                )
                lbl_style = "color:#F8FAFC; font-weight:500;"
            elif status == "active":
                circle = (
                    f'<div style="width:26px;height:26px;border-radius:50%;background:#3B82F6;'
                    f'display:flex;align-items:center;justify-content:center;font-size:0.7rem;'
                    f'font-weight:700;color:#fff;flex-shrink:0;">{idx+1}</div>'
                )
                lbl_style = "color:#3B82F6; font-weight:600;"
            else:
                circle = (
                    f'<div style="width:26px;height:26px;border-radius:50%;border:1px solid #1E293B;'
                    f'display:flex;align-items:center;justify-content:center;font-size:0.7rem;'
                    f'font-weight:600;color:#475569;flex-shrink:0;">{idx+1}</div>'
                )
                lbl_style = "color:#475569;"

            conn = (
                '<div style="width:1px;height:16px;background:#1E293B;margin-left:12px;"></div>'
                if idx < len(steps) - 1 else ""
            )

            stepper_html += f"""
            <div style="display:flex;align-items:center;gap:10px;">
              {circle}
              <span style="font-size:0.82rem;{lbl_style}">{label}</span>
            </div>
            {conn}"""
        stepper_html += "</div>"
        st.markdown(stepper_html, unsafe_allow_html=True)

        # ── Risk score ───────────────────────────────────────────────
        if step >= 1 and st.session_state.data:
            risk  = st.session_state.data["risk"]
            score = risk.get("overall_score")
            lbl   = risk.get("overall_label", "")
            if score is not None:
                st.markdown('<hr style="border:none;border-top:1px solid #1E293B;margin:0.5rem 0">', unsafe_allow_html=True)
                score_int  = round(score)
                bar_green  = '<span style="color:#22C55E;font-size:0.8rem;line-height:1;">●</span>' * score_int
                bar_empty  = '<span style="color:#1E293B;font-size:0.8rem;line-height:1;">●</span>' * (10 - score_int)
                score_color = "#22C55E" if score >= 7 else "#F59E0B" if score >= 5 else "#EF4444"
                st.markdown(
                    f'<div style="padding:0 0.25rem;">'
                    f'<div style="font-size:0.6rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Risk Score</div>'
                    f'<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:5px;">'
                    f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:1.5rem;font-weight:700;color:{score_color};">{score:.0f}</span>'
                    f'<span style="font-size:0.75rem;color:#475569;">/ 10</span>'
                    f'</div>'
                    f'<div style="margin-bottom:4px;">{bar_green}{bar_empty}</div>'
                    f'<div style="font-size:0.72rem;color:#94A3B8;">{lbl}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if step > 0:
            st.markdown('<hr style="border:none;border-top:1px solid #1E293B;margin:1rem 0">', unsafe_allow_html=True)
            if st.button("← New Analysis", use_container_width=True):
                st.session_state.update(step=0, ticker="", data=None, dcf=None, sens=None)
                st.rerun()


# ─── Step 0: Landing ──────────────────────────────────────────────────────────

def _render_landing() -> None:
    st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)

    # Badge
    st.markdown("""
    <div class="au" style="display:flex;justify-content:center;margin-bottom:0;">
      <div class="hero-badge">
        <div class="hero-badge-dot"></div>
        DCF Valuation Engine &nbsp;·&nbsp; Live Market Data
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Headline
    st.markdown("""
    <div class="au1" style="text-align:center;">
      <div class="hero-title">
        Institutional-grade valuation<br>
        <span class="hero-accent">in seconds.</span>
      </div>
    </div>
    <div class="au2" style="display:flex;justify-content:center;width:100%;">
      <p class="hero-sub" style="text-align:center;">
        Enter any US stock ticker. Get a full DCF model, risk assessment,
        and sensitivity analysis — powered by live financial data.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # Stats row
    st.markdown("""
    <div class="au2 hero-stats">
      <div class="hero-stat">
        <div class="hero-stat-val">5-yr</div>
        <div class="hero-stat-lbl">FCF Projection</div>
      </div>
      <div class="hero-divider"></div>
      <div class="hero-stat">
        <div class="hero-stat-val">WACC</div>
        <div class="hero-stat-lbl">CAPM Build-up</div>
      </div>
      <div class="hero-divider"></div>
      <div class="hero-stat">
        <div class="hero-stat-val">6</div>
        <div class="hero-stat-lbl">Risk Metrics</div>
      </div>
      <div class="hero-divider"></div>
      <div class="hero-stat">
        <div class="hero-stat-val">2×</div>
        <div class="hero-stat-lbl">Sensitivity Grids</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Input
    _, inp_col, _ = st.columns([1, 2, 1])
    with inp_col:
        ticker_input = st.text_input(
            "ticker",
            placeholder="Enter ticker symbol  (e.g. AAPL, TSLA, NVDA)",
            label_visibility="collapsed",
            key="landing_ticker",
        ).upper().strip()

        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)

        if st.button("Analyze Stock →", use_container_width=True):
            if not ticker_input:
                st.error("Please enter a ticker symbol.")
            else:
                with st.spinner(f"Fetching data for {ticker_input}…"):
                    data = _load_ticker_data(ticker_input)
                if data["fin"].get("market_data", {}).get("current_price") is None:
                    st.error(f"Could not find **{ticker_input}**. Check the symbol and try again.")
                else:
                    st.session_state.update(ticker=ticker_input, data=data, step=1)
                    st.rerun()

        # Quick picks
        st.markdown("""
        <div class="au3" style="text-align:center;margin-top:1rem;margin-bottom:0.4rem;">
          <span style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;">Quick picks</span>
        </div>
        """, unsafe_allow_html=True)
        chip_c1, chip_c2, chip_c3, chip_c4 = st.columns(4)
        for col, sym in [(chip_c1, "AAPL"), (chip_c2, "MSFT"), (chip_c3, "NVDA"), (chip_c4, "GOOGL")]:
            with col:
                if st.button(sym, use_container_width=True, key=f"chip_{sym}"):
                    with st.spinner(f"Loading {sym}…"):
                        data = _load_ticker_data(sym)
                    if data["fin"].get("market_data", {}).get("current_price") is None:
                        st.error(f"Could not find **{sym}**.")
                    else:
                        st.session_state.update(ticker=sym, data=data, step=1)
                        st.rerun()

    # Feature cards
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    _, cards_col, _ = st.columns([0.1, 3, 0.1])
    with cards_col:
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            st.markdown("""
            <div class="feat-card au2">
              <div class="feat-icon-wrap">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
              </div>
              <div class="feat-title">Live Financial Data</div>
              <div class="feat-desc">Pulls real-time income statements, balance sheets, beta, and Treasury yield from market APIs automatically.</div>
            </div>
            """, unsafe_allow_html=True)
        with fc2:
            st.markdown("""
            <div class="feat-card au3">
              <div class="feat-icon-wrap">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="2" width="16" height="20" rx="2"/>
                  <line x1="8" y1="7" x2="16" y2="7"/>
                  <line x1="8" y1="12" x2="16" y2="12"/>
                  <line x1="8" y1="17" x2="12" y2="17"/>
                </svg>
              </div>
              <div class="feat-title">Full DCF Engine</div>
              <div class="feat-desc">Projects free cash flows over 5 years with CAPM-based WACC, then discounts terminal value to implied share price.</div>
            </div>
            """, unsafe_allow_html=True)
        with fc3:
            st.markdown("""
            <div class="feat-card au4">
              <div class="feat-icon-wrap">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="3" width="7" height="7" rx="1"/>
                  <rect x="14" y="3" width="7" height="7" rx="1"/>
                  <rect x="14" y="14" width="7" height="7" rx="1"/>
                  <rect x="3" y="14" width="7" height="7" rx="1"/>
                </svg>
              </div>
              <div class="feat-title">Sensitivity Analysis</div>
              <div class="feat-desc">Two interactive heatmaps show how the valuation shifts across WACC, terminal growth, revenue growth, and EBIT margin.</div>
            </div>
            """, unsafe_allow_html=True)



# ─── Risk metric descriptions ─────────────────────────────────────────────────

_RISK_DESC: dict[str, str] = {
    "Leverage  (Debt / EBIT)":               "How many years of operating profit it would take to repay all debt — lower is safer.",
    "Interest Coverage  (EBIT / Interest)":  "Whether earnings comfortably cover interest payments — higher means less financial stress.",
    "FCF Volatility  (σ of FCF/EBIT)":       "How consistent free cash flow is relative to earnings — stable FCF makes forecasting more reliable.",
    "Revenue Consistency  (σ of YoY growth)":"Whether revenue grows steadily — erratic sales make future projections less certain.",
    "Debt Trend  (Total Debt CAGR)":          "Whether total debt is rising or falling — a rising trend increases financial risk over time.",
    "FCF Trend  (normalised slope)":          "Whether free cash flow is improving or deteriorating — a positive trend signals a strengthening business.",
}


# ─── Step 1a: Company snapshot ────────────────────────────────────────────────

def _render_snapshot(data: dict) -> None:
    fin  = data["fin"]
    mkt  = fin.get("market_data", {})
    pd_  = data["price_data"]
    risk = data["risk"]

    # 1-year price chart
    dates  = pd_["dates"]
    prices = pd_.get("prices", [])
    if dates and prices:
        up         = prices[-1] >= prices[0]
        line_color = "#22C55E" if up else "#EF4444"
        fill_color = "rgba(34,197,94,0.06)" if up else "rgba(239,68,68,0.06)"
        pct_chg    = (prices[-1] / prices[0] - 1)
        chg_label  = f"{'▲' if up else '▼'} {abs(pct_chg):.1%} past year"

        fig = go.Figure(go.Scatter(
            x=dates, y=prices, mode="lines",
            line=dict(color=line_color, width=1.5),
            fill="tozeroy", fillcolor=fill_color,
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(
                text=f"1-Year Price History  ·  {chg_label}",
                font=dict(size=12, color="#475569", family="Inter"),
            ),
            height=220, margin=dict(l=55, r=20, t=36, b=28),
            showlegend=False,
            plot_bgcolor="#0F172A", paper_bgcolor="#020617",
            xaxis=dict(
                showgrid=False, zeroline=False,
                tickfont=dict(size=10, color="#475569"),
                color="#475569",
            ),
            yaxis=dict(
                showgrid=True, gridcolor="#1E293B", zeroline=False,
                tickprefix="$", tickformat=",.0f",
                tickfont=dict(size=10, color="#475569"),
                color="#475569",
            ),
            font=dict(family="Inter, sans-serif", color="#F8FAFC"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Price history unavailable.")

    # Risk table
    with st.expander("Risk Dashboard", expanded=False):
        st.markdown(
            '<p style="font-size:0.82rem;color:#94A3B8;margin:0 0 0.75rem;line-height:1.6;">'
            'Six financial health checks, each rated '
            '<span style="color:#22C55E;font-weight:600;">● Healthy</span> &nbsp;·&nbsp; '
            '<span style="color:#F59E0B;font-weight:600;">● Watch</span> &nbsp;·&nbsp; '
            '<span style="color:#EF4444;font-weight:600;">● Concern</span>. '
            'The overall score (0–10) is shown in the sidebar.</p>',
            unsafe_allow_html=True,
        )
        metrics = risk.get("metrics", {})
        COLOR_MAP = {
            "green": ("rgba(34,197,94,0.2)",  "#22C55E"),
            "amber": ("rgba(245,158,11,0.2)", "#F59E0B"),
            "red":   ("rgba(239,68,68,0.2)",  "#EF4444"),
            "na":    ("#1E293B",               "#334155"),
        }
        cards_html = '<div class="risk-grid">'
        for m in metrics.values():
            border_color, accent_color = COLOR_MAP.get(m["rating"], ("#1E293B", "#334155"))
            val_color = accent_color if m["rating"] != "na" else "#475569"
            thresh = _RISK_DESC.get(m["label"], "")
            cards_html += (
                f'<div class="risk-card" style="border-color:{border_color};">'
                f'<div class="risk-card-header">'
                f'<div class="risk-dot" style="background:{accent_color};"></div>'
                f'<div class="risk-name">{m["label"]}</div>'
                f'</div>'
                f'<div class="risk-val" style="color:{val_color};">{m["value_str"]}</div>'
                f'<div class="risk-note">{m["note"]}</div>'
                f'<div class="risk-thresh">{thresh}</div>'
                f'</div>'
            )
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)


# ─── Step 1b: Historical FCF ──────────────────────────────────────────────────

def _render_fcf_table(data: dict) -> None:
    fcf    = data["fcf"]
    annual = fcf.get("annual", {})
    years  = sorted(annual.keys())

    _sec("Historical Free Cash Flow")
    st.caption(
        "FCF is the cash generated after funding operations and capital investments — "
        "the core input to the DCF model. FCF/EBIT shows what fraction of operating profit converts to real cash."
    )

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
            st.caption("† FCF = Operating CF − CapEx (from cash flow statement; ΔNWC-based formula unavailable)")
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
        st.warning("High FCF/EBIT volatility detected — forecast sensitivity will be wider.")


# ─── Step 1c: Assumptions panel ───────────────────────────────────────────────

def _render_assumptions(data: dict, ticker: str) -> dict[str, Any]:
    assum = data["assum"]
    mkt   = data["fin"].get("market_data", {})
    k     = ticker

    _sec("Forecast Assumptions")
    st.caption(
        "These inputs drive the entire DCF model — small changes here can move the implied price significantly. "
        "Values are pre-filled from live data and analyst estimates; adjust them to reflect your own view."
    )

    with st.expander("Revenue Growth", expanded=True):
        st.caption(
            "The annual rate at which the company's revenues are expected to grow over the 5-year forecast period. "
            "Pick a preset or enter a custom figure."
        )
        options: dict[str, float | None] = {}
        arg = assum.get("analyst_revenue_growth", {})

        v = assum.get("revenue_cagr_3yr", {}).get("value")
        if v is not None:
            options[f"Historical 3yr CAGR  ({v:.2%})"] = v
        v = assum.get("revenue_cagr_5yr", {}).get("value")
        if v is not None:
            options[f"Historical 5yr CAGR  ({v:.2%})"] = v

        v = arg.get("next_year", {}).get("value")
        if v is not None:
            options[f"Analyst estimate — next FY  ({v:.2%})"] = v
        v = arg.get("current_year", {}).get("value")
        if v is not None:
            options[f"Analyst estimate — current FY  ({v:.2%})"] = v

        _rev = (data["fin"].get("income_statement") or {}).get("revenue") or {}
        _ry  = sorted(yr for yr, val in _rev.items() if val is not None)
        if len(_ry) >= 2:
            _y1, _y0 = _ry[-1], _ry[-2]
            _r1, _r0 = _rev[_y1], _rev[_y0]
            if _r0 and _r1 and _r0 > 0:
                _yoy = (_r1 - _r0) / _r0
                options[f"Recent YoY Growth  FY{_y0}→FY{_y1}  ({_yoy:.2%})"] = _yoy

        _CUSTOM = "Custom..."
        options[_CUSTOM] = None

        selected = st.radio("", list(options.keys()),
                            label_visibility="collapsed",
                            key=f"{k}_growth_radio")
        if selected == _CUSTOM:
            growth_rate = st.number_input(
                "Growth rate (%)", value=5.0, min_value=-50.0, max_value=100.0,
                step=0.1, format="%.1f",
                help="Enter your own annual revenue growth assumption for the 5-year forecast.",
                key=f"{k}_growth_custom",
            ) / 100
        else:
            growth_rate = options[selected]

    with st.expander("EBIT Margin & Terminal Growth", expanded=False):
        st.caption(
            "EBIT margin is operating profit as a share of revenue — it determines how much of each sales dollar "
            "flows through to cash. Terminal growth rate is the assumed growth rate after year 5, in perpetuity."
        )
        base_margin = assum.get("ebit_margin_avg", {}).get("value") or 0.20
        col_em, col_tg = st.columns(2)
        with col_em:
            ebit_margin_pct = st.slider(
                "EBIT Margin", 0.0, 60.0,
                round(base_margin * 100, 1), 0.1, format="%.1f%%",
                help=f"Historical average: {_pct(base_margin)}.",
                key=f"{k}_ebit_slider",
            )
        with col_tg:
            tgr_pct = st.slider(
                "Terminal Growth Rate", 0.5, 5.0, 2.5, 0.1, format="%.1f%%",
                help="Assumed long-run FCF growth rate in perpetuity. Should not exceed GDP growth (2–3%).",
                key=f"{k}_tgr_slider",
            )

    with st.expander("WACC Assumptions", expanded=False):
        st.caption(
            "WACC is the discount rate applied to future cash flows — "
            "a higher WACC means future cash is worth less today, producing a lower implied price."
        )

        rfr_def  = (assum.get("risk_free_rate",      {}).get("value") or 0.0425) * 100
        erp_def  = (assum.get("equity_risk_premium", {}).get("value") or 0.045)  * 100
        beta_def =  mkt.get("beta") or 1.0
        kd_def   = (assum.get("cost_of_debt",        {}).get("value") or 0.04)   * 100
        tc_def   = (assum.get("effective_tax_rate",  {}).get("value") or 0.21)   * 100
        cs       = assum.get("capital_structure") or {}
        eq_w_def = (cs.get("equity_weight") or 0.90) * 100
        de_w_def = (cs.get("debt_weight")   or 0.10) * 100

        c1, c2, c3 = st.columns(3)
        with c1:
            rfr  = st.number_input(
                "Risk-free Rate (%)", value=rfr_def, step=0.05, format="%.2f", key=f"{k}_rfr",
                help="10-year US Treasury yield — the baseline return investors require.",
            )
            erp  = st.number_input(
                "Equity Risk Premium (%)", value=erp_def, step=0.05, format="%.2f", key=f"{k}_erp",
                help="Extra return demanded for owning stocks vs risk-free bonds. Typically 4–6% for the US.",
            )
            beta = st.number_input(
                "Beta", value=beta_def, step=0.01, format="%.2f", key=f"{k}_beta",
                help="Stock volatility relative to the market. >1 = more volatile.",
            )
        with c2:
            kd   = st.number_input(
                "Cost of Debt (%)", value=kd_def, step=0.05, format="%.2f", key=f"{k}_kd",
                help="Average interest rate the company pays on its debt.",
            )
            tc   = st.number_input(
                "Tax Rate (%)", value=tc_def, step=0.10, format="%.1f", key=f"{k}_tc",
                help="Effective corporate tax rate — used to compute the tax shield on debt.",
            )
        with c3:
            eq_w = st.number_input(
                "Equity Weight (%)", value=eq_w_def, step=0.50, format="%.1f", key=f"{k}_eqw",
                help="Equity as % of total capital (market cap ÷ (market cap + total debt)).",
            )
            de_w = st.number_input(
                "Debt Weight (%)", value=de_w_def, step=0.50, format="%.1f", key=f"{k}_dew",
                help="Debt as % of total capital.",
            )

        weight_sum = eq_w + de_w
        if abs(weight_sum - 100.0) > 0.1:
            st.warning(f"Equity Weight + Debt Weight = {weight_sum:.1f}% (should sum to 100%). WACC preview may be incorrect.")

        ke_prev   = (rfr / 100) + beta * (erp / 100)
        kd_at_pre = (kd  / 100) * (1 - tc / 100)
        wacc_pre  = ke_prev * (eq_w / 100) + kd_at_pre * (de_w / 100)

        st.markdown(f"""
        <div class="wacc-box">
          <div>
            <div style="font-size:0.6rem;font-weight:700;color:#475569;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:4px;">WACC Preview</div>
            <div class="wacc-val">{wacc_pre:.2%}</div>
          </div>
          <div class="wacc-detail">
            Ke &nbsp;= {rfr:.2f}% + {beta:.2f} × {erp:.2f}%
            &nbsp;= <span style="color:#F8FAFC;font-family:'IBM Plex Mono',monospace;">{ke_prev:.2%}</span><br>
            Kd(AT) = <span style="color:#F8FAFC;font-family:'IBM Plex Mono',monospace;">{kd_at_pre:.2%}</span>
            &nbsp;·&nbsp;
            WACC = <span style="color:#3B82F6;font-family:'IBM Plex Mono',monospace;font-weight:600;">{wacc_pre:.2%}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    return dict(
        growth_rate=growth_rate, ebit_margin=ebit_margin_pct / 100,
        tgr=tgr_pct / 100, rfr=rfr / 100, erp=erp / 100, beta=beta,
        kd=kd / 100, tc=tc / 100, eq_w=eq_w / 100, de_w=de_w / 100,
    )


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


# ─── Step 2: Results ──────────────────────────────────────────────────────────

def _render_results(dcf: dict, sens: dict | None) -> None:
    _sec("Valuation Results")
    st.caption(
        "The DCF model projects free cash flows over 5 years, computes a terminal value for everything beyond, "
        "and discounts both back to today using WACC. Compare the implied price to the current price for upside / downside."
    )

    ud  = dcf.get("upside_downside")
    imp = dcf.get("implied_share_price")
    cur = dcf.get("current_price")

    # ── Result hero ───────────────────────────────────────────────────
    if ud is not None:
        sign   = "+" if ud >= 0 else ""
        ud_cls = "pos" if ud >= 0 else "neg"
        _, col_hero, _ = st.columns([1, 2, 1])
        with col_hero:
            st.markdown(f"""
            <div class="result-hero">
              <div class="result-lbl">Implied Share Price</div>
              <div class="result-price">{_px(imp)}</div>
              <div class="result-cur">vs {_px(cur)} current market price</div>
              <div class="result-badge {ud_cls}">{sign}{ud:.1%}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Narrative ─────────────────────────────────────────────────────
    if ud is not None and imp is not None:
        inp       = dcf.get("inputs", {})
        wb        = dcf.get("wacc_buildup", {})
        pv_tv     = dcf.get("pv_terminal_value")
        ev        = dcf.get("enterprise_value")
        tv_pct    = (pv_tv / ev * 100) if (pv_tv and ev) else None
        direction = "undervalued" if ud >= 0 else "overvalued"
        col_dir   = "#22C55E" if ud >= 0 else "#EF4444"
        tv_note   = f" — {tv_pct:.0f}% of EV from terminal value" if tv_pct else ""
        st.markdown(f"""
        <div class="narrative">
          <strong>Model summary:</strong>
          At a WACC of <span style="color:#3B82F6;font-family:'IBM Plex Mono',monospace;">{_pct(wb.get('wacc'))}</span>,
          with revenue growing at <span style="color:#3B82F6;font-family:'IBM Plex Mono',monospace;">{_pct(inp.get('revenue_growth_rate'))}</span>
          and EBIT margins of <span style="color:#3B82F6;font-family:'IBM Plex Mono',monospace;">{_pct(inp.get('ebit_margin'))}</span>,
          the stock appears <span style="color:{col_dir};font-weight:600;">{direction}</span>
          versus its current price of {_px(cur)}.
          Terminal growth rate: <span style="color:#3B82F6;font-family:'IBM Plex Mono',monospace;">{_pct(inp.get('terminal_growth_rate'))}</span>{tv_note}.
          Use the sensitivity tables below to stress-test these assumptions.
        </div>
        """, unsafe_allow_html=True)

    # ── WACC build-up + bridge ────────────────────────────────────────
    col_wacc, col_bridge = st.columns(2)

    with col_wacc:
        _sec("WACC Build-Up")
        st.markdown('<p style="min-height:2.6rem;font-size:0.82rem;color:#94A3B8;line-height:1.55;margin:0 0 0.5rem;">Blends cost of equity (CAPM: RFR + β × ERP) with after-tax cost of debt, weighted by capital structure.</p>', unsafe_allow_html=True)
        wb = dcf.get("wacc_buildup", {})
        _htable(
            ["Component", "Value"],
            [
                ["Risk-free Rate",         _pct(wb.get("risk_free_rate"))],
                ["Beta",                   _x(  wb.get("beta"))],
                ["Equity Risk Premium",    _pct(wb.get("equity_risk_premium"))],
                ["Cost of Equity (CAPM)",  _pct(wb.get("cost_of_equity"))],
                ["Cost of Debt (pre-tax)", _pct(wb.get("cost_of_debt_pretax"))],
                ["After-tax Cost of Debt", _pct(wb.get("after_tax_cost_of_debt"))],
                ["Equity Weight",          _pct(wb.get("equity_weight"))],
                ["Debt Weight",            _pct(wb.get("debt_weight"))],
                ["WACC",                   _pct(wb.get("wacc"))],
            ],
            highlight_last=True,
        )

    with col_bridge:
        _sec("Equity Bridge")
        st.markdown('<p style="min-height:2.6rem;font-size:0.82rem;color:#94A3B8;line-height:1.55;margin:0 0 0.5rem;">Enterprise Value minus net debt, divided by shares outstanding = implied value per share.</p>', unsafe_allow_html=True)
        bridge = dcf.get("bridge", {})
        ev     = dcf.get("enterprise_value")
        pv_sum = dcf.get("pv_fcf_sum")
        pv_tv  = dcf.get("pv_terminal_value")
        tv_pct = (pv_tv / ev * 100) if (pv_tv and ev) else None
        shs    = bridge.get("shares_outstanding")
        shs_s  = f"{shs/1e9:.2f}B" if shs else "—"
        tv_s   = _bil(pv_tv) + (f'  <span class="muted">({tv_pct:.0f}% of EV)</span>'
                                 if tv_pct else "")
        imp_cls = "pos" if (ud or 0) >= 0 else "neg"
        imp_s  = f'<span class="{imp_cls}">{_px(imp)}</span>'

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
            highlight_last=False,
        )

    _hr()

    # ── FCF projection ────────────────────────────────────────────────
    _sec("5-Year FCF Projection")
    st.caption("Revenue grows at the selected rate; EBIT margin converts revenue to profit; FCF/EBIT converts to cash flow. Each year is discounted back to today at WACC.")
    proj    = dcf.get("projection", {})
    inp     = dcf.get("inputs", {})
    base_yr = dcf.get("base_year")
    base_rv = dcf.get("base_revenue")
    years   = sorted(proj.keys())

    if years:
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
        fig_bar  = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="Projected FCF",
            x=yr_lbls,
            y=[v / 1e9 if v is not None else None for v in fcf_vals],
            marker_color="#3B82F6",
            hovertemplate="<b>%{x}</b><br>FCF: $%{y:.2f}B<extra></extra>",
        ))
        fig_bar.add_trace(go.Bar(
            name="PV of FCF",
            x=yr_lbls,
            y=[v / 1e9 if v is not None else None for v in pv_vals],
            marker_color="rgba(59,130,246,0.35)",
            marker_line=dict(color="#3B82F6", width=1),
            hovertemplate="<b>%{x}</b><br>PV: $%{y:.2f}B<extra></extra>",
        ))
        fig_bar.update_layout(
            barmode="group",
            height=240,
            margin=dict(l=60, r=20, t=36, b=32),
            plot_bgcolor="#0F172A", paper_bgcolor="#020617",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=10, color="#94A3B8"),
                bgcolor="rgba(0,0,0,0)",
            ),
            yaxis=dict(
                tickprefix="$", ticksuffix="B",
                showgrid=True, gridcolor="#1E293B", zeroline=False,
                tickfont=dict(size=10, color="#475569"), color="#475569",
            ),
            xaxis=dict(
                showgrid=False, zeroline=False,
                tickfont=dict(size=10, color="#475569"), color="#475569",
            ),
            font=dict(family="Inter, sans-serif", color="#F8FAFC"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    warns = dcf.get("warnings", [])
    if warns:
        with st.expander(f"{len(warns)} valuation warning(s)", expanded=False):
            for w in warns:
                st.warning(w)

    # ── Sensitivity heatmaps ──────────────────────────────────────────
    if sens:
        _hr()
        _sec("Sensitivity Analysis")
        st.caption("Each cell shows the implied upside/downside when two key assumptions shift simultaneously. The blue-outlined cell is your base case.")
        tab1, tab2 = st.tabs([
            "WACC × Terminal Growth Rate",
            "Revenue Growth × EBIT Margin",
        ])
        with tab1:
            st.caption("Lower WACC or higher terminal growth both raise the implied price.")
            t1 = sens.get("table1")
            if t1:
                _render_heatmap(t1, "WACC", "Terminal Growth Rate")
        with tab2:
            st.caption("Companies with fast growth and wide margins command the highest valuations.")
            t2 = sens.get("table2")
            if t2:
                _render_heatmap(t2, "Revenue Growth", "EBIT Margin")


# ─── Sensitivity heatmap ──────────────────────────────────────────────────────

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

    z_plot    = z_data[::-1]
    t_plot    = text_data[::-1]
    row_lbls  = [f"{v:.2%}" for v in reversed(row_values)]
    col_lbls  = [f"{v:.1%}" for v in col_values]
    b_row_inv = n_rows - 1 - b_row

    x_coords = list(range(n_cols))
    y_coords = list(range(n_rows))

    flat = [v for row in z_plot for v in row if v is not None]
    zmax = max((abs(v) for v in flat), default=20)
    zmax = max(zmax, 5)

    custom = []
    for ri, rl in enumerate(row_lbls):
        custom.append([[rl, col_lbls[ci]] for ci in range(n_cols)])

    fig = go.Figure(go.Heatmap(
        z=z_plot, x=x_coords, y=y_coords,
        text=t_plot, texttemplate="%{text}",
        textfont=dict(size=11, family="'IBM Plex Mono', monospace", color="#F8FAFC"),
        customdata=custom,
        colorscale=[
            [0.00, "#EF4444"],
            [0.40, "#7F1D1D"],
            [0.50, "#1E293B"],
            [0.60, "#14532D"],
            [1.00, "#22C55E"],
        ],
        zmin=-zmax, zmid=0, zmax=zmax,
        colorbar=dict(
            title=dict(text="Upside %", font=dict(family="Inter", size=11, color="#475569")),
            tickformat=".0f", ticksuffix="%",
            tickfont=dict(family="Inter", size=10, color="#475569"),
            tickcolor="#334155",
            bgcolor="#0F172A",
            bordercolor="#1E293B",
            thickness=12, len=0.85,
        ),
        hovertemplate=(
            f"<b>{row_label}</b>: %{{customdata[0]}}<br>"
            f"<b>{col_label}</b>: %{{customdata[1]}}<br>"
            "<b>Upside</b>: %{text}<extra></extra>"
        ),
    ))

    # Base-case highlight — blue border
    fig.add_shape(
        type="rect",
        xref="x", yref="y",
        x0=b_col - 0.5, x1=b_col + 0.5,
        y0=b_row_inv - 0.5, y1=b_row_inv + 0.5,
        line=dict(color="#3B82F6", width=2.5),
        fillcolor="rgba(59,130,246,0.08)",
    )

    fig.update_layout(
        xaxis=dict(
            title=dict(text=col_label, font=dict(size=11, color="#475569")),
            tickmode="array", tickvals=x_coords, ticktext=col_lbls,
            showgrid=False, zeroline=False,
            tickfont=dict(color="#475569", size=10),
            color="#475569",
        ),
        yaxis=dict(
            title=dict(text=row_label, font=dict(size=11, color="#475569")),
            tickmode="array", tickvals=y_coords, ticktext=row_lbls,
            showgrid=False, zeroline=False,
            tickfont=dict(color="#475569", size=10),
            color="#475569",
        ),
        height=420,
        margin=dict(l=80, r=80, t=16, b=60),
        font=dict(family="Inter, sans-serif", size=11, color="#F8FAFC"),
        plot_bgcolor="#1E293B",
        paper_bgcolor="#0F172A",
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
        bear_color = "#EF4444" if bear_val < 0 else "#22C55E"
        bull_color = "#22C55E" if bull_val > 0 else "#EF4444"
        st.markdown(f"""
        <div style="display:flex;justify-content:center;gap:8px;margin-top:6px;margin-bottom:4px;">
          <div style="text-align:center;background:#0F172A;border:1px solid rgba(239,68,68,0.3);
                      border-radius:8px;padding:8px 20px;min-width:110px;">
            <div style="font-size:0.6rem;font-weight:700;color:#475569;text-transform:uppercase;
                        letter-spacing:0.09em;margin-bottom:4px;">Bear Case</div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:1rem;font-weight:700;
                        color:{bear_color};">{bear_val:+.1%}</div>
          </div>
          <div style="text-align:center;background:#0F172A;border:1px solid rgba(59,130,246,0.3);
                      border-radius:8px;padding:8px 20px;min-width:110px;">
            <div style="font-size:0.6rem;font-weight:700;color:#475569;text-transform:uppercase;
                        letter-spacing:0.09em;margin-bottom:4px;">Base Case</div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:1rem;font-weight:700;
                        color:#3B82F6;">{base_val:+.1%}</div>
          </div>
          <div style="text-align:center;background:#0F172A;border:1px solid rgba(34,197,94,0.3);
                      border-radius:8px;padding:8px 20px;min-width:110px;">
            <div style="font-size:0.6rem;font-weight:700;color:#475569;text-transform:uppercase;
                        letter-spacing:0.09em;margin-bottom:4px;">Bull Case</div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:1rem;font-weight:700;
                        color:{bull_color};">{bull_val:+.1%}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()
    st.markdown(_CSS, unsafe_allow_html=True)
    _render_sidebar()

    step   = st.session_state.step
    ticker = st.session_state.ticker

    if step == 0:
        _render_landing()
        return

    data = st.session_state.data
    if data is None:
        st.session_state.step = 0
        st.rerun()
        return

    # ── Top company bar ───────────────────────────────────────────────
    ci     = data["company_info"]
    mkt    = data["fin"].get("market_data", {})
    cur    = mkt.get("current_price")
    mcap   = mkt.get("market_cap")
    beta   = mkt.get("beta")
    prices = data["price_data"].get("prices", [])

    # 1yr price change
    if len(prices) >= 2:
        pct_chg   = (prices[-1] / prices[0] - 1)
        chg_arrow = "▲" if pct_chg >= 0 else "▼"
        chg_color = "#22C55E" if pct_chg >= 0 else "#EF4444"
        chg_html  = (
            f'<span style="font-size:0.8rem;font-family:\'IBM Plex Mono\',monospace;'
            f'color:{chg_color};font-weight:500;">'
            f'{chg_arrow} {abs(pct_chg):.1%} 1yr</span>'
        )
    else:
        chg_html = ""

    mcap_str = _bil(mcap) if mcap else ""
    beta_str = f"{beta:.2f}" if beta else ""
    industry = ci.get("industry", "") or ""

    st.markdown(f"""
    <div style="
      background: linear-gradient(135deg, #0F172A 0%, #0B1120 100%);
      border: 1px solid #1E293B;
      border-top: 2px solid #3B82F6;
      border-radius: 14px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.75rem;
      display: flex; align-items: center;
      justify-content: space-between; flex-wrap: wrap; gap: 16px;
    ">
      <!-- Left: identity -->
      <div style="display:flex; align-items:center; gap:18px;">
        <div>
          <div style="font-family:'IBM Plex Mono',monospace; font-size:2.1rem;
                      font-weight:700; color:#F8FAFC; letter-spacing:-0.03em; line-height:1.1;">
            {ticker}
          </div>
          <div style="font-size:0.82rem; color:#94A3B8; margin-top:4px; font-weight:400;">
            {ci.get('name','')}
          </div>
        </div>
        <div style="width:1px; height:44px; background:#1E293B; flex-shrink:0;"></div>
        <div style="display:flex; flex-direction:column; gap:5px;">
          <span style="
            display:inline-block; font-size:0.68rem; font-weight:700; color:#3B82F6;
            background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.25);
            border-radius:5px; padding:2px 9px; letter-spacing:0.05em;
          ">{ci.get('sector','')}</span>
          <span style="font-size:0.72rem; color:#475569;">{industry}</span>
        </div>
      </div>
      <!-- Right: price -->
      <div style="text-align:right; display:flex; flex-direction:column; gap:4px;">
        <div style="font-family:'IBM Plex Mono',monospace; font-size:2.1rem;
                    font-weight:700; color:#F8FAFC; letter-spacing:-0.03em; line-height:1.1;">
          {_px(cur) if cur else '—'}
        </div>
        <div style="display:flex; align-items:center; gap:12px; justify-content:flex-end; flex-wrap:wrap;">
          {chg_html}
          {'<span style="font-size:0.75rem;color:#334155;">|</span>' if chg_html and mcap_str else ''}
          {'<span style="font-size:0.75rem;color:#475569;">Mkt Cap <span style=\'font-family:IBM Plex Mono,monospace;color:#94A3B8;\'>' + mcap_str + '</span></span>' if mcap_str else ''}
          {'<span style="font-size:0.75rem;color:#334155;">|</span>' if mcap_str and beta_str else ''}
          {'<span style="font-size:0.75rem;color:#475569;">β <span style=\'font-family:IBM Plex Mono,monospace;color:#94A3B8;\'>' + beta_str + '</span></span>' if beta_str else ''}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _render_snapshot(data)
    _hr()
    _render_fcf_table(data)
    _hr()

    user_vals = _render_assumptions(data, ticker)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    ke_strip   = user_vals["rfr"] + user_vals["beta"] * user_vals["erp"]
    kd_at_strip = user_vals["kd"] * (1 - user_vals["tc"])
    wacc_strip = ke_strip * user_vals["eq_w"] + kd_at_strip * user_vals["de_w"]
    st.markdown(f"""
    <div class="assumption-strip">
      <span class="astrip-label">Running with</span>
      <span class="astrip-chip">Rev Growth {user_vals["growth_rate"]:.1%}</span>
      <span class="astrip-sep">·</span>
      <span class="astrip-chip">EBIT Margin {user_vals["ebit_margin"]:.1%}</span>
      <span class="astrip-sep">·</span>
      <span class="astrip-chip">TGR {user_vals["tgr"]:.1%}</span>
      <span class="astrip-sep">·</span>
      <span class="astrip-chip">WACC ~{wacc_strip:.1%}</span>
    </div>
    """, unsafe_allow_html=True)

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        run_clicked = st.button("Run Valuation →", use_container_width=True, key="run_btn")

    if run_clicked:
        assum_mod, fin_mod = _apply_overrides(data, user_vals)
        with st.spinner("Running DCF model…"):
            dcf = run_dcf(
                ticker_symbol=ticker, assumptions=assum_mod,
                fcf_result=data["fcf"], financial_data=fin_mod,
                revenue_growth_rate=user_vals["growth_rate"],
                terminal_growth_rate=user_vals["tgr"],
                ebit_margin_override=user_vals["ebit_margin"],
            )
        with st.spinner("Computing sensitivity grids…"):
            sens = build_sensitivity(
                ticker_symbol=ticker, base_dcf=dcf,
                assumptions=assum_mod, fcf_result=data["fcf"],
                financial_data=fin_mod,
            )
        st.session_state.update(dcf=dcf, sens=sens, step=2)
        st.rerun()

    if step >= 2 and st.session_state.dcf is not None:
        _hr()
        _render_results(st.session_state.dcf, st.session_state.sens)


if __name__ == "__main__":
    main()
