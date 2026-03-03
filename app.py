"""
app.py
------
Streamlit DCF Valuation Tool — polished UI with animations.
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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── CSS design system ──────────────────────────────────────────────────────

_CSS_BASE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, input, button, textarea, select,
.stMarkdown, .stText, .stMetric, .stDataFrame,
[data-testid="stSidebar"] { font-family: 'Inter', -apple-system, sans-serif !important; }

.main .block-container { padding: 2rem 2.5rem 4rem; max-width: 1100px; }

/* ── Animations ──────────────────────────────────── */
@keyframes fadeInUp {
  from { opacity:0; transform:translateY(18px); }
  to   { opacity:1; transform:translateY(0);    }
}
@keyframes scaleIn {
  from { opacity:0; transform:scale(0.90); }
  to   { opacity:1; transform:scale(1);    }
}
@keyframes popIn {
  0%   { opacity:0; transform:scale(0.80); }
  70%  { transform:scale(1.04); }
  100% { opacity:1; transform:scale(1);    }
}

.au  { animation: fadeInUp 0.5s ease both; }
.au1 { animation: fadeInUp 0.5s ease 0.08s both; }
.au2 { animation: fadeInUp 0.5s ease 0.16s both; }
.au3 { animation: fadeInUp 0.5s ease 0.24s both; }
.au4 { animation: fadeInUp 0.5s ease 0.32s both; }
.si  { animation: scaleIn  0.55s cubic-bezier(0.34,1.56,0.64,1) both; }
.pi  { animation: popIn    0.65s cubic-bezier(0.34,1.56,0.64,1) both; }

/* ── KPI cards ───────────────────────────────────── */
.kpi-row  { display:flex; gap:0.75rem; flex-wrap:wrap; margin-bottom:1.25rem; }
.kpi-card {
  flex:1; min-width:130px;
  background:#fff;
  border:1px solid #f0f4f8;
  border-radius:14px;
  padding:1rem 1.25rem;
  box-shadow:0 1px 4px rgba(0,0,0,.05),0 4px 16px rgba(0,0,0,.04);
  transition:transform .18s ease, box-shadow .18s ease;
  animation:fadeInUp .4s ease both;
}
.kpi-card:hover { transform:translateY(-3px); box-shadow:0 6px 22px rgba(0,0,0,.09); }
.kpi-lbl { font-size:.68rem; font-weight:600; color:#94a3b8; text-transform:uppercase;
           letter-spacing:.07em; margin-bottom:.3rem; }
.kpi-val { font-size:1.25rem; font-weight:700; color:#0f172a; white-space:nowrap; }
.kpi-sub { font-size:.72rem; color:#94a3b8; margin-top:.2rem; }

/* ── Result hero ─────────────────────────────────── */
.result-hero {
  border-radius:20px; padding:1.8rem 1.5rem; text-align:center;
  animation:popIn .65s cubic-bezier(0.34,1.56,0.64,1) both;
  margin:0.5rem 0 1.5rem;
}
.result-hero.pos { background:linear-gradient(135deg,#f0fdf4,#dcfce7); border:1px solid #86efac; }
.result-hero.neg { background:linear-gradient(135deg,#fff1f2,#ffe4e6); border:1px solid #fca5a5; }
.result-pct      { font-size:4.5rem; font-weight:800; line-height:1.05; }
.result-pct.pos  { color:#15803d; }
.result-pct.neg  { color:#b91c1c; }
.result-dir      { font-size:.85rem; font-weight:700; letter-spacing:.15em; margin-top:.4rem; }
.result-dir.pos  { color:#16a34a; }
.result-dir.neg  { color:#dc2626; }
.result-sub      { font-size:.82rem; color:#64748b; margin-top:.3rem; }

/* ── HTML table ──────────────────────────────────── */
.htable { width:100%; border-collapse:collapse; font-size:.855rem;
          animation:fadeInUp .4s ease both; }
.htable th {
  background:#f8fafc; color:#64748b; font-weight:600; font-size:.70rem;
  text-transform:uppercase; letter-spacing:.06em;
  padding:.6rem .9rem; border-bottom:2px solid #e2e8f0;
  text-align:right; white-space:nowrap;
}
.htable th:first-child { text-align:left; }
.htable td {
  padding:.52rem .9rem; border-bottom:1px solid #f1f5f9;
  text-align:right; color:#334155;
}
.htable td:first-child { text-align:left; font-weight:500; color:#0f172a; }
.htable tr:last-child td { border-bottom:none; }
.htable tr.hl   td { background:#eff6ff; font-weight:700; }
.htable tr.hlg  td { background:#f0fdf4; font-weight:700; color:#15803d; }
.pos { color:#16a34a; font-weight:600; }
.neg { color:#b91c1c; font-weight:600; }
.muted { color:#94a3b8; }

/* ── Section header ──────────────────────────────── */
.sec { font-size:1.05rem; font-weight:700; color:#0f172a;
       padding-bottom:.55rem; border-bottom:2px solid #f1f5f9;
       margin:1.5rem 0 .9rem; animation:fadeInUp .4s ease both; }

/* ── Sidebar ─────────────────────────────────────── */
[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#0f172a 0%,#1e293b 100%) !important;
}
[data-testid="stSidebar"] * { color:#cbd5e1 !important; }
[data-testid="stSidebar"] code {
  background:rgba(255,255,255,.12) !important;
  color:#f1f5f9 !important;
  border-radius:4px; padding:.1em .35em;
}
[data-testid="stSidebar"] hr { border-color:#334155 !important; }
[data-testid="stSidebar"] .stButton>button {
  background:rgba(255,255,255,.07) !important;
  border:1px solid rgba(255,255,255,.12) !important;
  color:#e2e8f0 !important; border-radius:8px !important;
  transition:background .2s !important;
}
[data-testid="stSidebar"] .stButton>button:hover {
  background:rgba(255,255,255,.13) !important;
}

/* ── Primary button ──────────────────────────────── */
.stButton>button[kind="primary"] {
  background:linear-gradient(135deg,#3b82f6,#6366f1) !important;
  border:none !important; border-radius:10px !important;
  font-weight:600 !important; font-size:1rem !important;
  padding:.65rem 2rem !important;
  box-shadow:0 4px 14px rgba(59,130,246,.35) !important;
  transition:transform .15s ease, box-shadow .15s ease !important;
}
.stButton>button[kind="primary"]:hover {
  transform:translateY(-2px) !important;
  box-shadow:0 6px 22px rgba(59,130,246,.45) !important;
}
.stButton>button[kind="primary"]:active { transform:translateY(0) !important; }
</style>
"""

_CSS_LANDING = """
<style>
.stApp { background:linear-gradient(135deg,#0f172a 0%,#1a2744 50%,#0f172a 100%) !important; }
.main .block-container { max-width:100% !important; padding:0 !important; }
.stTextInput>div>div>input {
  background:#1e293b !important;
  border:1px solid rgba(255,255,255,.18) !important;
  border-radius:10px !important; color:#fff !important;
  font-size:1.05rem !important; padding:.75rem 1rem !important;
  transition:border-color .2s, box-shadow .2s !important;
}
.stTextInput>div>div>input::placeholder { color:rgba(255,255,255,.35) !important; }
.stTextInput>div>div>input:focus {
  border-color:#60a5fa !important;
  box-shadow:0 0 0 3px rgba(96,165,250,.2) !important;
}
.stTextInput label { color:rgba(255,255,255,0) !important; height:0 !important;
                     overflow:hidden !important; }
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
    # v3 — OCF / FCF alias fixes applied; bust stale cloud cache
    fin         = fetch_financial_data(symbol)
    fcf         = calculate_fcf(fin)
    assum       = build_assumptions(symbol, fin)
    risk_result = assess_risk(fin, fcf)

    t = yf.Ticker(symbol)
    info: dict = {}
    hist = pd.DataFrame()
    try:
        info = t.info or {}
    except Exception:
        pass
    try:
        hist = t.history(period="1y")
    except Exception:
        pass

    company_info = {
        "name":     info.get("longName") or info.get("shortName") or symbol,
        "sector":   info.get("sector",   "N/A"),
        "industry": info.get("industry", "N/A"),
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

def _kpi(label: str, value: str, sub: str = "", delay: int = 0) -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    d = f"animation-delay:{delay*0.08}s"
    return (f'<div class="kpi-card" style="{d}">'
            f'<div class="kpi-lbl">{label}</div>'
            f'<div class="kpi-val">{value}</div>{sub_html}</div>')

def _kpi_row(items: list[tuple]) -> None:
    """Render a row of KPI cards. items = [(label, value, sub_optional), ...]"""
    html = '<div class="kpi-row">'
    for i, item in enumerate(items):
        label, value = item[0], item[1]
        sub = item[2] if len(item) > 2 else ""
        html += _kpi(label, value, sub, i)
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def _htable(headers: list[str], rows: list[list], highlight_last: bool = False) -> None:
    """Render a styled HTML table."""
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for i, row in enumerate(rows):
        is_last  = i == len(rows) - 1
        row_cls  = ' class="hl"' if (highlight_last and is_last) else ""
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        body += f"<tr{row_cls}>{tds}</tr>"
    st.markdown(
        f'<table class="htable"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>',
        unsafe_allow_html=True,
    )

def _sec(title: str) -> None:
    st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────

def _render_sidebar() -> None:
    step   = st.session_state.step
    ticker = st.session_state.ticker

    with st.sidebar:
        st.markdown("## 📊 DCF Valuation")
        if ticker:
            st.markdown(f"### {ticker}")
        st.divider()

        st.markdown("**Progress**")
        for req, label in [
            (1, "Company Snapshot"),
            (1, "Historical FCF"),
            (1, "Risk Assessment"),
            (1, "Assumptions"),
            (2, "Valuation Results"),
            (2, "Sensitivity Analysis"),
        ]:
            icon = "✅" if step >= req else ("▶" if step == req - 1 else "○")
            st.markdown(f"{icon}  {label}")

        if step >= 1 and st.session_state.data:
            risk  = st.session_state.data["risk"]
            score = risk.get("overall_score")
            lbl   = risk.get("overall_label", "")
            if score is not None:
                st.divider()
                filled = round(score)
                bar    = "🟢" * filled + "⚫" * (10 - filled)
                st.markdown(f"**Risk Score**  \n{bar}  \n**{score:.0f}/10** — {lbl}")

        if step > 0:
            st.divider()
            if st.button("← New Analysis", use_container_width=True):
                st.session_state.update(step=0, ticker="", data=None, dcf=None, sens=None)
                st.rerun()


# ─── Step 0: Landing ────────────────────────────────────────────────────────

def _render_landing() -> None:
    st.markdown(_CSS_LANDING, unsafe_allow_html=True)

    col_l, col_r = st.columns([1.15, 1], gap="large")

    with col_l:
        st.markdown("""
        <div style="padding:4rem 1rem 2rem 3rem;">
          <div class="au" style="margin-bottom:.6rem;">
            <span style="background:rgba(99,102,241,.22);color:#a5b4fc;
                  padding:.3rem .9rem;border-radius:999px;font-size:.78rem;font-weight:600;">
              Automated Equity Research
            </span>
          </div>
          <h1 class="au1" style="font-size:3.4rem;font-weight:800;margin:.8rem 0 .5rem;
              background:linear-gradient(100deg,#60a5fa 0%,#a78bfa 50%,#f0abfc 100%);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent;
              background-clip:text;line-height:1.08;">
            DCF Valuation
          </h1>
          <p class="au2" style="color:#94a3b8;font-size:1.05rem;line-height:1.75;
              margin-bottom:2.5rem;max-width:400px;">
            Live financials → DCF model → sensitivity analysis.<br>
            In seconds, for any US stock.
          </p>
        </div>
        """, unsafe_allow_html=True)

        _, inp_col, _ = st.columns([0.18, 1, 0.05])
        with inp_col:
            ticker_input = st.text_input(
                "ticker",
                placeholder="Enter ticker — e.g. AAPL, MSFT, GOOGL",
                label_visibility="collapsed",
            ).upper().strip()
            st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

            if st.button("Analyse →", type="primary", use_container_width=True):
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

    with col_r:
        st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
        if _LOTTIE_OK:
            lottie_data = _load_lottie()
            if lottie_data:
                st_lottie(lottie_data, height=380, speed=0.9,
                          loop=True, quality="high", key="hero_lottie")
                return
        # Fallback: decorative text if lottie unavailable
        st.markdown("""
        <div style="display:flex;align-items:center;justify-content:center;
                    height:380px;font-size:6rem;opacity:.15;">📈</div>
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

    _kpi_row([
        ("Company",     ci["name"]),
        ("Sector",      ci["sector"]),
        ("Price",       _px(curr_price)),
        ("Market Cap",  _bil(market_cap)),
        ("Beta",        f"{beta:.2f}" if beta else "—"),
        ("Risk Score",  f"{score:.0f}/10" if score is not None else "—", rlabel),
    ])

    # ── 1-year price chart ────────────────────────────────────────────
    dates  = pd_["dates"]
    prices = pd_["prices"]
    if dates and prices:
        up         = prices[-1] >= prices[0]
        line_color = "#16a34a" if up else "#ef4444"
        fill_color = "rgba(22,163,74,0.07)" if up else "rgba(239,68,68,0.07)"
        pct_chg    = (prices[-1] / prices[0] - 1)
        chg_str    = f"{'▲' if up else '▼'} {abs(pct_chg):.1%} past year"

        fig = go.Figure(go.Scatter(
            x=dates, y=prices, mode="lines",
            line=dict(color=line_color, width=2),
            fill="tozeroy", fillcolor=fill_color,
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text=f"1-Year Price  ·  {chg_str}",
                       font=dict(size=13, color="#64748b")),
            height=240, margin=dict(l=50, r=20, t=38, b=28),
            showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor="#f1f5f9", zeroline=False,
                       tickprefix="$", tickformat=",.0f", tickfont=dict(size=11)),
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Price history unavailable.")

    # ── Risk table (collapsed) ────────────────────────────────────────
    with st.expander("📋  Risk Assessment", expanded=False):
        metrics = risk.get("metrics", {})
        BADGE   = {"green": "🟢", "amber": "🟡", "red": "🔴", "na": "⚪"}
        rows = [
            [m["label"], m["value_str"],
             BADGE.get(m["rating"], "?"), m["note"]]
            for m in metrics.values()
        ]
        _htable(["Metric", "Value", "Rating", "Note"], rows)


# ─── Step 1b: Historical FCF ────────────────────────────────────────────────

def _render_fcf_table(data: dict) -> None:
    fcf    = data["fcf"]
    annual = fcf.get("annual", {})
    years  = sorted(annual.keys())

    _sec("Historical Free Cash Flow")

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
                row.append(f"{v:.2f}×{sup}")
            else:
                cls = _val_cls(v) if key == "fcf" else ""
                sup = " †" if key == "fcf" and method in ("direct", "reported") else ""
                txt = f"{_bil(v)}{sup}"
                row.append(f'<span class="{cls}">{txt}</span>' if cls else txt)
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
        st.warning("⚠️ High FCF/EBIT volatility detected.")


# ─── Step 1c: Assumptions panel ─────────────────────────────────────────────

def _render_assumptions(data: dict, ticker: str) -> dict[str, Any]:
    assum = data["assum"]
    mkt   = data["fin"].get("market_data", {})
    k     = ticker

    _sec("Forecast Assumptions")

    with st.expander("📈  Revenue Growth", expanded=True):
        options: dict[str, float] = {}
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

        if not options:
            st.error("No revenue growth estimates available.")
            growth_rate = 0.05
        else:
            selected    = st.radio("", list(options.keys()),
                                   label_visibility="collapsed",
                                   key=f"{k}_growth_radio")
            growth_rate = options[selected]

    with st.expander("📊  EBIT Margin & Terminal Growth", expanded=True):
        base_margin = assum.get("ebit_margin_avg", {}).get("value") or 0.20
        col_em, col_tg = st.columns(2)
        with col_em:
            ebit_margin_pct = st.slider(
                "EBIT Margin", 0.0, 60.0,
                round(base_margin * 100, 1), 0.1, format="%.1f%%",
                help=f"Historical avg: {_pct(base_margin)}",
                key=f"{k}_ebit_slider",
            )
        with col_tg:
            tgr_pct = st.slider(
                "Terminal Growth Rate", 0.5, 5.0, 2.5, 0.1, format="%.1f%%",
                help="Gordon Growth perpetuity rate (typically 2–3%)",
                key=f"{k}_tgr_slider",
            )

    with st.expander("⚙️  WACC Assumptions", expanded=True):
        st.caption("Values in % (e.g. `4.25` for 4.25%). Beta is dimensionless.")

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
            rfr  = st.number_input("Risk-free Rate (%)",      value=rfr_def,  step=0.05, format="%.2f", key=f"{k}_rfr")
            erp  = st.number_input("Equity Risk Premium (%)", value=erp_def,  step=0.05, format="%.2f", key=f"{k}_erp")
            beta = st.number_input("Beta",                    value=beta_def, step=0.01, format="%.2f", key=f"{k}_beta")
        with c2:
            kd   = st.number_input("Cost of Debt (%)",        value=kd_def,   step=0.05, format="%.2f", key=f"{k}_kd")
            tc   = st.number_input("Tax Rate (%)",            value=tc_def,   step=0.10, format="%.1f", key=f"{k}_tc")
        with c3:
            eq_w = st.number_input("Equity Weight (%)",       value=eq_w_def, step=0.50, format="%.1f", key=f"{k}_eqw")
            de_w = st.number_input("Debt Weight (%)",         value=de_w_def, step=0.50, format="%.1f", key=f"{k}_dew")

        ke_prev   = (rfr / 100) + beta * (erp / 100)
        kd_at_pre = (kd  / 100) * (1 - tc / 100)
        wacc_pre  = ke_prev * (eq_w / 100) + kd_at_pre * (de_w / 100)
        st.info(
            f"**WACC preview** — "
            f"Ke = {rfr:.2f}% + {beta:.2f} × {erp:.2f}% = **{ke_prev:.2%}**  |  "
            f"Kd(AT) = **{kd_at_pre:.2%}**  |  **WACC = {wacc_pre:.2%}**"
        )

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

    ud  = dcf.get("upside_downside")
    imp = dcf.get("implied_share_price")
    cur = dcf.get("current_price")

    # ── Hero ──────────────────────────────────────────────────────────
    if ud is not None:
        sign    = "+" if ud >= 0 else ""
        cls     = "pos" if ud >= 0 else "neg"
        dir_txt = "▲  UPSIDE" if ud >= 0 else "▼  DOWNSIDE"
        _, col_hero, _ = st.columns([1, 2, 1])
        with col_hero:
            st.markdown(f"""
            <div class="result-hero {cls}">
              <div class="result-pct {cls}">{sign}{ud:.1%}</div>
              <div class="result-dir {cls}">{dir_txt}</div>
              <div class="result-sub">Implied {_px(imp)}  ·  Current {_px(cur)}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── WACC build-up + bridge ────────────────────────────────────────
    col_wacc, col_bridge = st.columns(2)

    with col_wacc:
        st.markdown('<div class="sec" style="margin-top:0">WACC Build-Up</div>',
                    unsafe_allow_html=True)
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
                ["<strong>WACC</strong>",  f"<strong>{_pct(wb.get('wacc'))}</strong>"],
            ],
            highlight_last=True,
        )

    with col_bridge:
        st.markdown('<div class="sec" style="margin-top:0">Equity Bridge</div>',
                    unsafe_allow_html=True)
        bridge = dcf.get("bridge", {})
        ev     = dcf.get("enterprise_value")
        pv_sum = dcf.get("pv_fcf_sum")
        pv_tv  = dcf.get("pv_terminal_value")
        tv_pct = (pv_tv / ev * 100) if (pv_tv and ev) else None
        shs    = bridge.get("shares_outstanding")
        shs_s  = f"{shs/1e9:.2f}B" if shs else "—"
        tv_s   = _bil(pv_tv) + (f"  <span class='muted'>({tv_pct:.0f}% of EV)</span>"
                                 if tv_pct else "")
        imp_s  = (f'<span class="{"pos" if (ud or 0) >= 0 else "neg"}">'
                  f'{_px(imp)}</span>')

        _htable(
            ["Item", "Value"],
            [
                ["PV of FCFs",          _bil(pv_sum)],
                ["PV of Terminal Value", tv_s],
                ["Enterprise Value",    _bil(ev)],
                ["(−) Total Debt",      _bil(bridge.get("total_debt"))],
                ["(+) Cash",            _bil(bridge.get("cash_and_equivalents"))],
                ["Equity Value",        _bil(bridge.get("equity_value"))],
                ["Shares Outstanding",  shs_s],
                [f"<strong>Implied Price</strong>", imp_s],
                ["Current Price",       _px(cur)],
            ],
            highlight_last=False,
        )

    st.divider()

    # ── FCF projection ────────────────────────────────────────────────
    st.markdown('<div class="sec">5-Year FCF Projection</div>', unsafe_allow_html=True)
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
        with st.expander(f"⚠️  {len(warns)} valuation warning(s)", expanded=False):
            for w in warns:
                st.warning(w)

    # ── Sensitivity heatmaps ──────────────────────────────────────────
    if sens:
        st.divider()
        st.markdown('<div class="sec">Sensitivity Analysis</div>', unsafe_allow_html=True)
        tab1, tab2 = st.tabs([
            "Table 1 — WACC × Terminal Growth Rate",
            "Table 2 — Revenue Growth × EBIT Margin",
        ])
        with tab1:
            t1 = sens.get("table1")
            if t1:
                _render_heatmap(t1, "WACC", "Terminal Growth Rate")
        with tab2:
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
        textfont=dict(size=11, family="Inter", color="#0f172a"),
        customdata=custom,
        colorscale=[
            [0.00, "#7f1d1d"],
            [0.25, "#fca5a5"],
            [0.50, "#f1f5f9"],
            [0.75, "#86efac"],
            [1.00, "#14532d"],
        ],
        zmin=-zmax, zmid=0, zmax=zmax,
        colorbar=dict(
            title=dict(text="Upside %", font=dict(family="Inter", size=12)),
            tickformat=".0f", ticksuffix="%",
            tickfont=dict(family="Inter", size=11),
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
        line=dict(color="#1d4ed8", width=3),
        fillcolor="rgba(29,78,216,0.08)",
    )

    fig.update_layout(
        xaxis=dict(
            title=dict(text=col_label, font=dict(size=12)),
            tickmode="array", tickvals=x_coords, ticktext=col_lbls,
            showgrid=False, zeroline=False,
        ),
        yaxis=dict(
            title=dict(text=row_label, font=dict(size=12)),
            tickmode="array", tickvals=y_coords, ticktext=row_lbls,
            showgrid=False, zeroline=False,
        ),
        height=420,
        margin=dict(l=80, r=80, t=16, b=60),
        font=dict(family="Inter, sans-serif", size=11),
        plot_bgcolor="#f8fafc",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Blue shading = base case assumptions")


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()
    st.markdown(_CSS_BASE, unsafe_allow_html=True)
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
    st.divider()
    _render_fcf_table(data)
    st.divider()

    user_vals = _render_assumptions(data, ticker)
    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        run_clicked = st.button("▶  Run Valuation", type="primary",
                                use_container_width=True, key="run_btn")

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
        st.divider()
        _render_results(st.session_state.dcf, st.session_state.sens)


if __name__ == "__main__":
    main()
