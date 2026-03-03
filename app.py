"""
app.py
------
Streamlit DCF Valuation Tool — professional dark theme UI.
"""

import copy
import requests
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from typing import Any

try:
    from streamlit_lottie import st_lottie
    _LOTTIE_OK = True
except ImportError:
    _LOTTIE_OK = False

from data_fetcher   import fetch_financial_data
from fcf_calculator import calculate_fcf
from assumptions    import build_assumptions
from dcf_engine     import run_dcf
from sensitivity    import build_sensitivity
from risk           import assess_risk


# ─── Page config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DCF Valuation",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── CSS design system ──────────────────────────────────────────────────────

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');
.material-symbols-outlined {
  font-family: 'Material Symbols Outlined';
  font-variation-settings: 'FILL' 0, 'wght' 300, 'GRAD' 0, 'opsz' 24;
  font-style: normal; line-height: 1; display: inline-block; white-space: nowrap;
  text-transform: none; word-wrap: normal; direction: ltr;
}
.feat-icon .material-symbols-outlined {
  font-size: 1.8rem; color: #6C63FF;
  background: rgba(108,99,255,0.12); border-radius: 10px;
  padding: 8px; display: inline-flex; align-items: center; justify-content: center;
}

/* Global */
html, body, [data-testid="stApp"] { background: #0A0A0F !important; }
html, body, input, button, textarea, select, .stMarkdown, [data-testid="stSidebar"] {
  font-family: 'Inter', -apple-system, sans-serif !important;
}
.main .block-container { padding: 2rem 2.5rem 4rem; max-width: 1200px; }

/* Hide Streamlit chrome */
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: #13131A !important;
  border-right: 1px solid #1E1E2E !important;
}

/* Cards */
.card {
  background: #13131A;
  border: 1px solid #1E1E2E;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}
.card-accent {
  border-left: 3px solid #6C63FF;
}

/* Buttons */
.stButton > button {
  background: #6C63FF !important;
  color: white !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  transition: background 0.2s !important;
}
.stButton > button:hover { background: #7C75FF !important; }

/* Sliders — style thumb only; do not override the track container */
[data-testid="stSlider"] [role="slider"] {
  background: #6C63FF !important;
  border: 2px solid #6C63FF !important;
  box-shadow: 0 0 0 3px rgba(108,99,255,0.25) !important;
}

/* Radio */
[data-testid="stRadio"] label { color: #E8E8F0 !important; }

/* Inputs */
[data-testid="stNumberInput"] input { color: #E8E8F0 !important; background: #1E1E2E !important; }

/* KPI cards (dark) */
.kpi-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.kpi-card {
  flex: 1; min-width: 140px;
  background: #13131A;
  border: 1px solid #1E1E2E;
  border-radius: 12px;
  padding: 16px 20px;
}
.kpi-lbl {
  font-size: 0.65rem; font-weight: 600; color: #6B6B80;
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;
}
.kpi-val {
  font-size: 1.5rem; font-weight: 700; color: #E8E8F0;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.kpi-sub { font-size: 0.7rem; color: #6B6B80; margin-top: 4px; }

/* Section headers */
.sec {
  font-size: 1.1rem; font-weight: 700; color: #E8E8F0;
  margin: 1.5rem 0 0.75rem; letter-spacing: -0.01em;
}

/* Tables */
.htable { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.htable th {
  background: #1E1E2E; color: #6B6B80;
  font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.07em; padding: 8px 12px; text-align: right;
}
.htable th:first-child { text-align: left; }
.htable td { padding: 9px 12px; color: #E8E8F0; border-bottom: 1px solid #1E1E2E; text-align: right; }
.htable td:first-child { text-align: left; color: #6B6B80; font-size: 0.83rem; }
.htable tr:last-child td { border-bottom: none; }
.htable tr:hover td { background: rgba(108,99,255,0.05); }
.num { font-family: 'SF Mono', 'Fira Code', monospace; }
.pos { color: #00D09C !important; }
.neg { color: #FF4757 !important; }
.muted { color: #6B6B80; }
.acc { color: #6C63FF !important; font-weight: 700; }

/* Result hero */
.result-hero {
  border-radius: 16px; padding: 2.5rem 2rem; text-align: center;
  background: #13131A; border: 1px solid #1E1E2E; margin: 0.5rem 0 2rem;
}
.result-price {
  font-size: 5rem; font-weight: 800; color: #E8E8F0;
  font-family: 'SF Mono', 'Fira Code', monospace;
  letter-spacing: -0.03em; line-height: 1.1;
}
.result-lbl { font-size: 0.75rem; color: #6B6B80; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem; }
.result-cur { font-size: 0.9rem; color: #6B6B80; margin-top: 0.5rem; }
.result-badge {
  display: inline-block; padding: 0.35rem 1rem;
  border-radius: 999px; font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 1.4rem; font-weight: 700; margin-top: 0.75rem;
}
.result-badge.pos { background: rgba(0,208,156,0.15); color: #00D09C; }
.result-badge.neg { background: rgba(255,71,87,0.15); color: #FF4757; }
.result-note { font-size: 0.83rem; color: #6B6B80; margin-top: 1rem; }

/* Landing */
.hero-title { font-size: 3.5rem; font-weight: 800; color: #E8E8F0; text-align: center; line-height: 1.15; margin-bottom: 0.5rem; }
.hero-accent { color: #6C63FF; }
.hero-sub { font-size: 1.05rem; color: #6B6B80; text-align: center; max-width: 480px; margin: 0 auto 2rem; }
.chip {
  display: inline-block; padding: 4px 14px;
  border: 1px solid #6C63FF; border-radius: 999px;
  color: #6C63FF; font-size: 0.78rem; font-weight: 600;
  cursor: pointer; margin: 0 4px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.feat-card {
  background: #13131A; border: 1px solid #1E1E2E;
  border-radius: 12px; padding: 20px; text-align: left;
}
.feat-icon { font-size: 1.6rem; margin-bottom: 10px; }
.feat-title { font-size: 0.95rem; font-weight: 700; color: #E8E8F0; margin-bottom: 6px; }
.feat-desc { font-size: 0.8rem; color: #6B6B80; line-height: 1.5; }

/* Animations */
@keyframes fadeInUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
.au  { animation: fadeInUp 0.45s ease both; }
.au1 { animation: fadeInUp 0.45s ease 0.08s both; }
.au2 { animation: fadeInUp 0.45s ease 0.16s both; }
.au3 { animation: fadeInUp 0.45s ease 0.24s both; }
</style>
"""


# ─── Lottie loader ──────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_lottie() -> dict | None:
    for url in [
        "https://assets2.lottiefiles.com/packages/lf20_kkflmtur.json",
        "https://assets9.lottiefiles.com/packages/lf20_qp1q7mct.json",
    ]:
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None


# ─── Session state ──────────────────────────────────────────────────────────

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


# ─── Data loading ────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def _load_ticker_data(symbol: str) -> dict[str, Any]:
    # v6 — fix beta fallback tz mismatch; bust stale cloud cache
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


# ─── Formatters ─────────────────────────────────────────────────────────────

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
    """CSS class for a numeric value."""
    if v is None or v == 0: return "muted"
    return "pos" if v > 0 else "neg"


# ─── HTML helpers ────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="kpi-card">'
            f'<div class="kpi-lbl">{label}</div>'
            f'<div class="kpi-val">{value}</div>{sub_html}</div>')

def _kpi_row(items: list[tuple]) -> None:
    """Render a row of KPI cards. items = [(label, value, sub_optional), ...]"""
    html = '<div class="kpi-row">'
    for item in items:
        label, value = item[0], item[1]
        sub = item[2] if len(item) > 2 else ""
        html += _kpi(label, value, sub)
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def _htable(headers: list[str], rows: list[list], highlight_last: bool = False) -> None:
    """Render a styled dark HTML table."""
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for i, row in enumerate(rows):
        is_last = i == len(rows) - 1
        tds = ""
        for j, cell in enumerate(row):
            # First column: label cell (left-aligned, handled by CSS)
            # Other columns: wrap numbers in .num span
            if j == 0:
                tds += f"<td>{cell}</td>"
            else:
                # If already wrapped in HTML tag, don't double-wrap
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
    st.markdown(f'<div class="sec">{text}</div>', unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────

def _render_sidebar() -> None:
    step   = st.session_state.step
    ticker = st.session_state.ticker

    with st.sidebar:
        if ticker and step > 0 and st.session_state.data:
            ci = st.session_state.data["company_info"]
            company_name = ci.get("name", ticker)
            st.markdown(f"""
            <div style="padding: 1rem 0.5rem;">
              <div style="font-family:'SF Mono','Fira Code',monospace; font-size:1.8rem;
                          font-weight:800; color:#6C63FF; letter-spacing:-0.02em;">{ticker}</div>
              <div style="font-size:0.8rem; color:#6B6B80; margin-bottom:1.5rem;">{company_name}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding: 1rem 0.5rem 0.5rem;">
              <div style="font-size:1.1rem; font-weight:700; color:#E8E8F0;">DCF Valuation</div>
              <div style="font-size:0.8rem; color:#6B6B80; margin-top:4px;">Institutional-grade analysis</div>
            </div>
            """, unsafe_allow_html=True)

        # 4-step stepper
        steps = [
            (1, "Snapshot"),
            (2, "Assumptions"),
            (3, "Valuation"),
            (4, "Results"),
        ]
        stepper_html = '<div style="padding: 0 0.5rem; margin-bottom: 1.5rem;">'
        for idx, (req, label) in enumerate(steps):
            if step >= req:
                # Completed
                circle = '<div style="width:28px;height:28px;border-radius:50%;background:#00D09C;display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;color:#0A0A0F;flex-shrink:0;">✓</div>'
                lbl_style = "color:#E8E8F0;"
            elif step == req - 1:
                # Active
                circle = f'<div style="width:28px;height:28px;border-radius:50%;background:#6C63FF;display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;color:#fff;flex-shrink:0;">{idx+1}</div>'
                lbl_style = "color:#6C63FF; font-weight:600;"
            else:
                # Future
                circle = f'<div style="width:28px;height:28px;border-radius:50%;border:1px solid #1E1E2E;display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:600;color:#6B6B80;flex-shrink:0;">{idx+1}</div>'
                lbl_style = "color:#6B6B80;"

            stepper_html += f"""
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
              {circle}
              <span style="font-size:0.85rem;{lbl_style}">{label}</span>
            </div>"""
        stepper_html += "</div>"
        st.markdown(stepper_html, unsafe_allow_html=True)

        # Risk score if available
        if step >= 1 and st.session_state.data:
            risk  = st.session_state.data["risk"]
            score = risk.get("overall_score")
            lbl   = risk.get("overall_label", "")
            if score is not None:
                st.markdown('<hr style="border:none;border-top:1px solid #1E1E2E;margin:0.5rem 0">', unsafe_allow_html=True)
                filled = round(score)
                bar    = '<span style="color:#00D09C;font-size:0.85rem;">●</span>' * filled + '<span style="color:#2A2A3A;font-size:0.85rem;">●</span>' * (10 - filled)
                st.markdown(
                    f'<div style="font-size:0.75rem;color:#6B6B80;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:6px;">Risk Score</div>'
                    f'<div style="font-size:0.85rem;color:#E8E8F0;margin-bottom:4px;">{bar}</div>'
                    f'<div style="font-family:\'SF Mono\',monospace;font-size:0.9rem;color:#E8E8F0;font-weight:600;">{score:.0f}/10</div>'
                    f'<div style="font-size:0.75rem;color:#6B6B80;">{lbl}</div>',
                    unsafe_allow_html=True,
                )

        if step > 0:
            st.markdown('<hr style="border:none;border-top:1px solid #1E1E2E;margin:1rem 0">', unsafe_allow_html=True)
            if st.button("← New Analysis", use_container_width=True):
                st.session_state.update(step=0, ticker="", data=None, dcf=None, sens=None)
                st.rerun()


# ─── Step 0: Landing ────────────────────────────────────────────────────────

def _render_landing() -> None:
    st.markdown("""
    <div class="au" style="text-align:center; padding: 3rem 0 1.5rem;">
      <div class="hero-title">Institutional-grade valuation<br><span class="hero-accent">in seconds.</span></div>
    </div>
    <div class="au1" style="text-align:center;">
      <p class="hero-sub">Enter any US stock ticker. Get a DCF valuation, sensitivity analysis, and risk assessment — powered by live market data.</p>
    </div>
    """, unsafe_allow_html=True)

    _, inp_col, _ = st.columns([1, 2, 1])
    with inp_col:
        ticker_input = st.text_input(
            "ticker",
            placeholder="e.g. AAPL, TSLA, NVDA",
            label_visibility="collapsed",
            key="landing_ticker",
        ).upper().strip()

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        if st.button("Search →", use_container_width=True):
            if not ticker_input:
                st.error("Please enter a ticker symbol.")
            else:
                with st.spinner(f"Loading {ticker_input}…"):
                    data = _load_ticker_data(ticker_input)
                if data["fin"].get("market_data", {}).get("current_price") is None:
                    st.error(f"Could not find **{ticker_input}**. Check the symbol.")
                else:
                    st.session_state.update(ticker=ticker_input, data=data, step=1)
                    st.rerun()

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        # Quick-pick chips
        st.markdown('<div style="text-align:center;margin-bottom:0.5rem;font-size:0.78rem;color:#6B6B80;">Quick picks</div>', unsafe_allow_html=True)
        chip_c1, chip_c2, chip_c3 = st.columns(3)
        for col, sym in [(chip_c1, "AAPL"), (chip_c2, "MSFT"), (chip_c3, "NVDA")]:
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
    st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        st.markdown("""
        <div class="feat-card au1">
          <div class="feat-icon"><span class="material-symbols-outlined">monitoring</span></div>
          <div class="feat-title">Live Data</div>
          <div class="feat-desc">Fetches real-time financials, beta, and Treasury yield automatically</div>
        </div>
        """, unsafe_allow_html=True)
    with fc2:
        st.markdown("""
        <div class="feat-card au2">
          <div class="feat-icon"><span class="material-symbols-outlined">calculate</span></div>
          <div class="feat-title">DCF Engine</div>
          <div class="feat-desc">Projects free cash flow using your verified assumptions</div>
        </div>
        """, unsafe_allow_html=True)
    with fc3:
        st.markdown("""
        <div class="feat-card au3">
          <div class="feat-icon"><span class="material-symbols-outlined">scatter_plot</span></div>
          <div class="feat-title">Sensitivity Analysis</div>
          <div class="feat-desc">See how valuation changes across WACC and growth scenarios</div>
        </div>
        """, unsafe_allow_html=True)


# ─── Step 1a: Company snapshot ──────────────────────────────────────────────

def _render_snapshot(data: dict) -> None:
    fin  = data["fin"]
    ci   = data["company_info"]
    mkt  = fin.get("market_data", {})
    pd_  = data["price_data"]
    risk = data["risk"]

    _sec("Company Snapshot")

    curr_price = mkt.get("current_price")
    market_cap = mkt.get("market_cap")
    beta       = mkt.get("beta")
    score      = risk.get("overall_score")
    rlabel     = risk.get("overall_label", "")

    # Price change over 1y
    prices = pd_.get("prices", [])
    if len(prices) >= 2:
        pct_chg = (prices[-1] / prices[0] - 1)
        chg_str = f"{'▲' if pct_chg >= 0 else '▼'} {abs(pct_chg):.1%} 1yr"
    else:
        chg_str = ""

    _kpi_row([
        ("Current Price",  _px(curr_price), chg_str),
        ("Market Cap",     _bil(market_cap)),
        ("Beta",           f"{beta:.2f}" if beta else "—"),
        ("Sector",         ci["sector"]),
        ("Risk Score",     f"{score:.0f}/10" if score is not None else "—", rlabel),
    ])

    # ── 1-year price chart ────────────────────────────────────────────
    dates  = pd_["dates"]
    if dates and prices:
        up         = prices[-1] >= prices[0]
        line_color = "#00D09C" if up else "#FF4757"
        fill_color = "rgba(0,208,156,0.08)" if up else "rgba(255,71,87,0.08)"
        pct_chg    = (prices[-1] / prices[0] - 1)
        chg_label  = f"{'▲' if up else '▼'} {abs(pct_chg):.1%} past year"

        fig = go.Figure(go.Scatter(
            x=dates, y=prices, mode="lines",
            line=dict(color=line_color, width=2),
            fill="tozeroy", fillcolor=fill_color,
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text=f"1-Year Price  ·  {chg_label}",
                       font=dict(size=13, color="#6B6B80")),
            height=240, margin=dict(l=50, r=20, t=38, b=28),
            showlegend=False,
            plot_bgcolor="#13131A", paper_bgcolor="#0A0A0F",
            xaxis=dict(showgrid=False, zeroline=False,
                       tickfont=dict(size=11, color="#6B6B80"),
                       color="#6B6B80"),
            yaxis=dict(showgrid=True, gridcolor="#1E1E2E", zeroline=False,
                       tickprefix="$", tickformat=",.0f",
                       tickfont=dict(size=11, color="#6B6B80"),
                       color="#6B6B80"),
            font=dict(family="Inter, sans-serif", color="#E8E8F0"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Price history unavailable.")

    # ── Risk table (collapsed) ────────────────────────────────────────
    _RISK_DESC = {
        "Leverage  (Debt / EBIT)":             "How many years of operating profit it would take to repay all debt — lower is safer.",
        "Interest Coverage  (EBIT / Interest)":"Whether earnings comfortably cover interest payments — higher means less financial stress.",
        "FCF Volatility  (σ of FCF/EBIT)":     "How consistent free cash flow is relative to earnings — stable FCF makes forecasting more reliable.",
        "Revenue Consistency  (σ of YoY growth)": "Whether revenue grows steadily — erratic sales make future projections less certain.",
        "Debt Trend  (Total Debt CAGR)":        "Whether total debt is rising or falling — a rising trend increases financial risk over time.",
        "FCF Trend  (normalised slope)":        "Whether free cash flow is improving or deteriorating — a positive trend signals a strengthening business.",
    }
    with st.expander("Risk Dashboard", expanded=False):
        st.caption(
            "Six financial health checks, each rated Healthy · Watch · Concern. "
            "The overall score (0–10) is shown in the sidebar."
        )
        metrics = risk.get("metrics", {})
        BADGE   = {
            "green": '<span style="color:#00D09C;">●</span>',
            "amber": '<span style="color:#F59E0B;">●</span>',
            "red":   '<span style="color:#FF4757;">●</span>',
            "na":    '<span style="color:#6B6B80;">●</span>',
        }
        rows = [
            [m["label"], m["value_str"],
             BADGE.get(m["rating"], "?"), m["note"],
             _RISK_DESC.get(m["label"], "")]
            for m in metrics.values()
        ]
        _htable(["Metric", "Value", "Rating", "Note", "What it measures"], rows)


# ─── Step 1b: Historical FCF ────────────────────────────────────────────────

def _render_fcf_table(data: dict) -> None:
    fcf    = data["fcf"]
    annual = fcf.get("annual", {})
    years  = sorted(annual.keys())

    _sec("Historical Free Cash Flow")
    st.caption(
        "Free Cash Flow (FCF) is the cash a company generates after funding its operations "
        "and capital investments — the core input to the DCF model. "
        "FCF/EBIT shows what fraction of operating profit actually converts to real cash."
    )

    if not years:
        st.info("No FCF data available.")
        return

    headers = [""] + [f"FY{yr}" for yr in years]
    rows_def = [
        ("EBIT",        "ebit",           False),
        ("D&A",         "da",             False),
        ("Operating CF","opcf",           False),
        ("ΔNWC",        "delta_nwc",      False),
        ("CapEx",       "capex",          False),
        ("FCF",         "fcf",            False),
        ("FCF / EBIT",  "fcf_ebit_ratio", True),
    ]

    # Track which fallback methods were used (for footnote)
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
        html = '<div class="kpi-row" style="flex-direction:column;">'
        if tc   is not None: html += _kpi("Effective Tax Rate", _pct(tc))
        if avg3 is not None: html += _kpi("FCF/EBIT  3yr avg",  _x(avg3))
        if avg5 is not None: html += _kpi("FCF/EBIT  5yr avg",  _x(avg5))
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    if fcf.get("fcf_ebit_volatility_flag"):
        st.warning("High FCF/EBIT volatility detected.")


# ─── Step 1c: Assumptions panel ─────────────────────────────────────────────

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

        # Analyst consensus estimates (requires quoteSummary endpoint;
        # may be unavailable on cloud-hosted environments).
        v = arg.get("next_year", {}).get("value")
        if v is not None:
            options[f"Analyst estimate — next FY  ({v:.2%})"] = v
        v = arg.get("current_year", {}).get("value")
        if v is not None:
            options[f"Analyst estimate — current FY  ({v:.2%})"] = v

        # Recent YoY growth from already-fetched financials — always available.
        _rev = (data["fin"].get("income_statement") or {}).get("revenue") or {}
        _ry  = sorted(yr for yr, val in _rev.items() if val is not None)
        if len(_ry) >= 2:
            _y1, _y0 = _ry[-1], _ry[-2]
            _r1, _r0 = _rev[_y1], _rev[_y0]
            if _r0 and _r1 and _r0 > 0:
                _yoy = (_r1 - _r0) / _r0
                options[f"Recent YoY Growth  FY{_y0}→FY{_y1}  ({_yoy:.2%})"] = _yoy

        _CUSTOM = "Custom..."
        options[_CUSTOM] = None  # always last

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

    with st.expander("EBIT Margin & Terminal Growth", expanded=True):
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
                help=(
                    f"Operating profit as a percentage of revenue. "
                    f"Historical average: {_pct(base_margin)}. "
                    "Higher margins mean more of each sales dollar converts to profit."
                ),
                key=f"{k}_ebit_slider",
            )
        with col_tg:
            tgr_pct = st.slider(
                "Terminal Growth Rate", 0.5, 5.0, 2.5, 0.1, format="%.1f%%",
                help=(
                    "The assumed annual growth rate of free cash flow beyond the 5-year forecast — "
                    "effectively forever. Should not exceed long-run GDP growth (typically 2–3%)."
                ),
                key=f"{k}_tgr_slider",
            )

    with st.expander("WACC Assumptions", expanded=True):
        st.caption(
            "WACC (Weighted Average Cost of Capital) is the discount rate applied to future cash flows — "
            "a higher WACC means future cash is worth less today, producing a lower implied price. "
            "Values in % (e.g. `4.25` for 4.25%). Beta is dimensionless."
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
                help="The yield on a risk-free asset such as the 10-year US Treasury — sets the baseline return investors require before taking any equity risk.",
            )
            erp  = st.number_input(
                "Equity Risk Premium (%)", value=erp_def, step=0.05, format="%.2f", key=f"{k}_erp",
                help="The extra return investors demand for owning stocks rather than risk-free bonds — typically 4–6% for the US market.",
            )
            beta = st.number_input(
                "Beta", value=beta_def, step=0.01, format="%.2f", key=f"{k}_beta",
                help="Measures how much the stock moves relative to the market. Beta > 1 means more volatile than the market; < 1 means less volatile.",
            )
        with c2:
            kd   = st.number_input(
                "Cost of Debt (%)", value=kd_def, step=0.05, format="%.2f", key=f"{k}_kd",
                help="The average interest rate the company pays on its debt. Used to compute the after-tax cost of debt (Kd × (1 − tax rate)).",
            )
            tc   = st.number_input(
                "Tax Rate (%)", value=tc_def, step=0.10, format="%.1f", key=f"{k}_tc",
                help="The effective corporate tax rate, used to calculate the tax shield on debt interest — debt is cheaper on an after-tax basis.",
            )
        with c3:
            eq_w = st.number_input(
                "Equity Weight (%)", value=eq_w_def, step=0.50, format="%.1f", key=f"{k}_eqw",
                help="Equity's share of total capital (market cap ÷ (market cap + total debt)). Equity is costlier than debt, so a higher equity weight raises WACC.",
            )
            de_w = st.number_input(
                "Debt Weight (%)", value=de_w_def, step=0.50, format="%.1f", key=f"{k}_dew",
                help="Debt's share of total capital. Because debt is cheaper than equity (especially after the tax shield), more debt lowers WACC.",
            )

        ke_prev   = (rfr / 100) + beta * (erp / 100)
        kd_at_pre = (kd  / 100) * (1 - tc / 100)
        wacc_pre  = ke_prev * (eq_w / 100) + kd_at_pre * (de_w / 100)

        # WACC live preview as large purple number
        st.markdown(f"""
        <div style="background:#1E1E2E;border-radius:10px;padding:16px 20px;margin-top:8px;display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
          <div>
            <div style="font-size:0.65rem;font-weight:600;color:#6B6B80;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;">WACC Preview</div>
            <div style="font-family:'SF Mono','Fira Code',monospace;font-size:2rem;font-weight:800;color:#6C63FF;">{wacc_pre:.2%}</div>
          </div>
          <div style="font-size:0.82rem;color:#6B6B80;line-height:1.6;">
            Ke = {rfr:.2f}% + {beta:.2f} × {erp:.2f}% = <span style="color:#E8E8F0;font-family:'SF Mono','Fira Code',monospace;">{ke_prev:.2%}</span><br>
            Kd(AT) = <span style="color:#E8E8F0;font-family:'SF Mono','Fira Code',monospace;">{kd_at_pre:.2%}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    return dict(
        growth_rate=growth_rate, ebit_margin=ebit_margin_pct / 100,
        tgr=tgr_pct / 100, rfr=rfr / 100, erp=erp / 100, beta=beta,
        kd=kd / 100, tc=tc / 100, eq_w=eq_w / 100, de_w=de_w / 100,
    )


# ─── Apply user overrides ────────────────────────────────────────────────────

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


# ─── Step 2: Results ────────────────────────────────────────────────────────

def _render_results(dcf: dict, sens: dict | None) -> None:
    _sec("Valuation Results")
    st.caption(
        "The DCF model projects free cash flows over 5 years, estimates a terminal value for everything beyond, "
        "and discounts both back to today using WACC. The implied price is what the model says the stock is worth "
        "under your assumptions — compare it to the current price to see upside or downside."
    )

    ud  = dcf.get("upside_downside")
    imp = dcf.get("implied_share_price")
    cur = dcf.get("current_price")

    # ── Hero ──────────────────────────────────────────────────────────
    if ud is not None:
        sign     = "+" if ud >= 0 else ""
        ud_cls   = "pos" if ud >= 0 else "neg"
        _, col_hero, _ = st.columns([1, 2, 1])
        with col_hero:
            st.markdown(f"""
            <div class="result-hero">
              <div class="result-lbl">Implied Share Price</div>
              <div class="result-price">{_px(imp)}</div>
              <div class="result-cur">vs {_px(cur)} current price</div>
              <div class="result-badge {ud_cls}">{sign}{ud:.1%}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── DCF narrative ─────────────────────────────────────────────────
    if ud is not None and imp is not None:
        inp       = dcf.get("inputs", {})
        wb        = dcf.get("wacc_buildup", {})
        pv_tv     = dcf.get("pv_terminal_value")
        ev        = dcf.get("enterprise_value")
        tv_pct    = (pv_tv / ev * 100) if (pv_tv and ev) else None
        direction = "undervalued" if ud >= 0 else "overvalued"
        tv_note   = f" — {tv_pct:.0f}% of Enterprise Value comes from the terminal value" if tv_pct else ""
        st.markdown(f"""
        <div style="background:#13131A;border:1px solid #1E1E2E;border-left:3px solid #6C63FF;
                    border-radius:10px;padding:14px 18px;margin-bottom:1.5rem;font-size:0.88rem;color:#6B6B80;line-height:1.65;">
          <span style="color:#E8E8F0;font-weight:600;">What the model is saying:</span>
          At a WACC of <span style="color:#6C63FF;font-family:'SF Mono','Fira Code',monospace;">{_pct(wb.get('wacc'))}</span>,
          growing revenue at <span style="color:#6C63FF;font-family:'SF Mono','Fira Code',monospace;">{_pct(inp.get('revenue_growth_rate'))}</span>
          with <span style="color:#6C63FF;font-family:'SF Mono','Fira Code',monospace;">{_pct(inp.get('ebit_margin'))}</span> EBIT margins,
          the business appears <span style="color:{'#00D09C' if ud >= 0 else '#FF4757'};font-weight:600;">{direction}</span>
          versus its current price of {_px(cur)}.
          The main driver of value is the terminal value assumption
          (long-run growth rate of <span style="color:#6C63FF;font-family:'SF Mono','Fira Code',monospace;">{_pct(inp.get('terminal_growth_rate'))}</span>){tv_note}.
          Use the sensitivity tables below to see how much the implied price changes if these assumptions shift.
        </div>
        """, unsafe_allow_html=True)

    # ── WACC build-up + bridge ────────────────────────────────────────
    col_wacc, col_bridge = st.columns(2)

    with col_wacc:
        _sec("WACC Build-Up")
        st.caption("WACC blends the cost of equity (RFR + β × ERP, via CAPM) with the after-tax cost of debt, weighted by capital structure. It is the discount rate applied to every projected cash flow.")
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
        st.caption("Enterprise Value is the total value of the business. Subtract net debt (debt minus cash) and divide by shares outstanding to arrive at the implied value per share.")
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

    st.markdown('<hr style="border:none;border-top:1px solid #1E1E2E;margin:1.5rem 0">', unsafe_allow_html=True)

    # ── FCF projection ────────────────────────────────────────────────
    _sec("5-Year FCF Projection")
    st.caption("Revenue grows at the selected rate; the EBIT margin converts revenue to operating profit; the FCF/EBIT ratio converts that to cash flow. Each year's FCF is then discounted back to today using WACC to get its present value.")
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

    warns = dcf.get("warnings", [])
    if warns:
        with st.expander(f"{len(warns)} valuation warning(s)", expanded=False):
            for w in warns:
                st.warning(w)

    # ── Sensitivity heatmaps ──────────────────────────────────────────
    if sens:
        st.markdown('<hr style="border:none;border-top:1px solid #1E1E2E;margin:1.5rem 0">', unsafe_allow_html=True)
        _sec("Sensitivity Analysis")
        st.caption("Each cell shows the implied upside or downside if two key assumptions change simultaneously. Green = model says the stock is undervalued; red = overvalued. The purple-outlined cell is your base case.")
        tab1, tab2 = st.tabs([
            "Table 1 — WACC × Terminal Growth Rate",
            "Table 2 — Revenue Growth × EBIT Margin",
        ])
        with tab1:
            st.caption("Vary the discount rate (WACC, vertical axis) and the long-run growth assumption (horizontal axis). Lower WACC or higher terminal growth both increase the implied price.")
            t1 = sens.get("table1")
            if t1:
                _render_heatmap(t1, "WACC", "Terminal Growth Rate")
        with tab2:
            st.caption("Vary the top-line growth rate (vertical axis) and the profit margin (horizontal axis). Companies with both fast growth and wide margins command the highest valuations.")
            t2 = sens.get("table2")
            if t2:
                _render_heatmap(t2, "Revenue Growth", "EBIT Margin")


# ─── Sensitivity heatmap ────────────────────────────────────────────────────

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

    # Reverse rows so the highest row value appears at the top of the chart
    z_plot    = z_data[::-1]
    t_plot    = text_data[::-1]
    row_lbls  = [f"{v:.2%}" for v in reversed(row_values)]
    col_lbls  = [f"{v:.1%}" for v in col_values]
    b_row_inv = n_rows - 1 - b_row

    # Use numeric axes with ticktext labels so shape coordinates are unambiguous
    x_coords = list(range(n_cols))
    y_coords = list(range(n_rows))

    flat = [v for row in z_plot for v in row if v is not None]
    zmax = max((abs(v) for v in flat), default=20)
    zmax = max(zmax, 5)

    # Build customdata (row_lbl, col_lbl) for hover
    custom = []
    for ri, rl in enumerate(row_lbls):
        custom.append([[rl, col_lbls[ci]] for ci in range(n_cols)])

    fig = go.Figure(go.Heatmap(
        z=z_plot, x=x_coords, y=y_coords,
        text=t_plot, texttemplate="%{text}",
        textfont=dict(size=11, family="'SF Mono', 'Fira Code', monospace", color="#E8E8F0"),
        customdata=custom,
        colorscale=[
            [0.00, "#FF4757"],
            [0.50, "#1E1E2E"],
            [1.00, "#00D09C"],
        ],
        zmin=-zmax, zmid=0, zmax=zmax,
        colorbar=dict(
            title=dict(text="Upside %", font=dict(family="Inter", size=12, color="#6B6B80")),
            tickformat=".0f", ticksuffix="%",
            tickfont=dict(family="Inter", size=11, color="#6B6B80"),
            tickcolor="#6B6B80",
            bgcolor="#13131A",
            bordercolor="#1E1E2E",
            thickness=14, len=0.85,
        ),
        hovertemplate=(
            f"<b>{row_label}</b>: %{{customdata[0]}}<br>"
            f"<b>{col_label}</b>: %{{customdata[1]}}<br>"
            "<b>Upside</b>: %{text}<extra></extra>"
        ),
    ))

    # Base-case highlight — numeric coords are exact category positions
    fig.add_shape(
        type="rect",
        xref="x", yref="y",
        x0=b_col - 0.5, x1=b_col + 0.5,
        y0=b_row_inv - 0.5, y1=b_row_inv + 0.5,
        line=dict(color="#6C63FF", width=3),
        fillcolor="rgba(108,99,255,0.12)",
    )

    fig.update_layout(
        xaxis=dict(
            title=dict(text=col_label, font=dict(size=12, color="#6B6B80")),
            tickmode="array", tickvals=x_coords, ticktext=col_lbls,
            showgrid=False, zeroline=False,
            tickfont=dict(color="#6B6B80"),
            color="#6B6B80",
        ),
        yaxis=dict(
            title=dict(text=row_label, font=dict(size=12, color="#6B6B80")),
            tickmode="array", tickvals=y_coords, ticktext=row_lbls,
            showgrid=False, zeroline=False,
            tickfont=dict(color="#6B6B80"),
            color="#6B6B80",
        ),
        height=420,
        margin=dict(l=80, r=80, t=16, b=60),
        font=dict(family="Inter, sans-serif", size=11, color="#E8E8F0"),
        plot_bgcolor="#1E1E2E",
        paper_bgcolor="#13131A",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Purple outline = base case assumptions")


# ─── Main ────────────────────────────────────────────────────────────────────

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

    _render_snapshot(data)
    st.markdown('<hr style="border:none;border-top:1px solid #1E1E2E;margin:1.5rem 0">', unsafe_allow_html=True)
    _render_fcf_table(data)
    st.markdown('<hr style="border:none;border-top:1px solid #1E1E2E;margin:1.5rem 0">', unsafe_allow_html=True)

    user_vals = _render_assumptions(data, ticker)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        run_clicked = st.button("Run Valuation →", use_container_width=True, key="run_btn")

    if run_clicked:
        assum_mod, fin_mod = _apply_overrides(data, user_vals)
        with st.spinner("Running DCF…"):
            dcf = run_dcf(
                ticker_symbol=ticker, assumptions=assum_mod,
                fcf_result=data["fcf"], financial_data=fin_mod,
                revenue_growth_rate=user_vals["growth_rate"],
                terminal_growth_rate=user_vals["tgr"],
                ebit_margin_override=user_vals["ebit_margin"],
            )
        with st.spinner("Running sensitivity grids…"):
            sens = build_sensitivity(
                ticker_symbol=ticker, base_dcf=dcf,
                assumptions=assum_mod, fcf_result=data["fcf"],
                financial_data=fin_mod,
            )
        st.session_state.update(dcf=dcf, sens=sens, step=2)
        st.rerun()

    if step >= 2 and st.session_state.dcf is not None:
        st.markdown('<hr style="border:none;border-top:1px solid #1E1E2E;margin:1.5rem 0">', unsafe_allow_html=True)
        _render_results(st.session_state.dcf, st.session_state.sens)


if __name__ == "__main__":
    main()
