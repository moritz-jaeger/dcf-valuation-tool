"""
app.py
------
Streamlit DCF Valuation Tool — multi-step web interface.

Wires together:
    data_fetcher  →  fcf_calculator  →  assumptions  →  dcf_engine
    →  sensitivity  →  risk
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


# ─── Page configuration ────────────────────────────────────────────────────

st.set_page_config(
    page_title="DCF Valuation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.main .block-container { padding: 2rem 2.5rem 3rem; max-width: 1100px; }

.big-upside   { font-size:3.5rem; font-weight:700; color:#16a34a; text-align:center; }
.big-downside { font-size:3.5rem; font-weight:700; color:#dc2626; text-align:center; }
.upside-sub   { font-size:1.05rem; color:#6b7280; text-align:center; margin-top:4px; }

div[data-testid="metric-container"] > div:first-child { font-size:.8rem; color:#6b7280; }
</style>
""", unsafe_allow_html=True)


# ─── Session state initialisation ──────────────────────────────────────────

def _init_state() -> None:
    defaults: dict[str, Any] = {
        "step":   0,      # 0 = landing | 1 = data loaded | 2 = valued
        "ticker": "",
        "data":   None,   # dict from _load_ticker_data()
        "dcf":    None,   # run_dcf() result
        "sens":   None,   # build_sensitivity() result
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ─── Data loading (cached) ─────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def _load_ticker_data(symbol: str) -> dict[str, Any]:
    """Fetch and compute all backend data for a ticker.  Cached 1 h."""
    fin         = fetch_financial_data(symbol)
    fcf         = calculate_fcf(fin)
    assum       = build_assumptions(symbol, fin)
    risk_result = assess_risk(fin, fcf)

    # Extra fields for company snapshot
    try:
        t    = yf.Ticker(symbol)
        info = t.info or {}
        hist = t.history(period="1y")
    except Exception:
        info = {}
        hist = pd.DataFrame()

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
        "fin":          fin,
        "fcf":          fcf,
        "assum":        assum,
        "risk":         risk_result,
        "company_info": company_info,
        "price_data":   price_data,
    }


# ─── Formatters ────────────────────────────────────────────────────────────

def _bil(v: float | None) -> str:
    if v is None:      return "N/A"
    if abs(v) >= 1e12: return f"${v/1e12:.2f}T"
    if abs(v) >= 1e9:  return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:  return f"${v/1e6:.1f}M"
    return f"${v:,.0f}"

def _pct(v: float | None, dp: int = 2) -> str:
    if v is None: return "N/A"
    return f"{v:.{dp}%}"

def _px(v: float | None) -> str:
    if v is None: return "N/A"
    return f"${v:,.2f}"

def _x(v: float | None) -> str:
    if v is None: return "N/A"
    return f"{v:.2f}×"


# ─── Sidebar ───────────────────────────────────────────────────────────────

def _render_sidebar() -> None:
    step   = st.session_state.step
    ticker = st.session_state.ticker

    with st.sidebar:
        st.markdown("## 📊 DCF Valuation")
        if ticker:
            st.markdown(f"**`{ticker}`**")
        st.divider()

        st.markdown("**Steps**")
        _step_row = lambda done, active, label: st.markdown(
            f"{'✅' if done else ('▶' if active else '○')}  {label}"
        )
        _step_row(step >= 1, step == 0, "Company Snapshot")
        _step_row(step >= 1, step == 0, "Historical FCF")
        _step_row(step >= 1, step == 0, "Risk Assessment")
        _step_row(step >= 1, step == 1, "Assumptions")
        _step_row(step >= 2, step == 1, "Valuation Results")
        _step_row(step >= 2, step == 1, "Sensitivity Analysis")

        if step >= 1 and st.session_state.data:
            risk   = st.session_state.data["risk"]
            score  = risk.get("overall_score")
            rlabel = risk.get("overall_label", "")
            if score is not None:
                st.divider()
                bar_green = round(score)
                bar_str   = "🟢" * bar_green + "⚫" * (10 - bar_green)
                st.markdown(f"**Risk Score**  \n{bar_str}  \n`{score:.0f}/10` — {rlabel}")

        if step > 0:
            st.divider()
            if st.button("← New Analysis", use_container_width=True):
                st.session_state.update(step=0, ticker="", data=None, dcf=None, sens=None)
                st.rerun()


# ─── Step 0: Landing ───────────────────────────────────────────────────────

def _render_landing() -> None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("# 📊 DCF Valuation")
        st.markdown(
            "Enter a US stock ticker to fetch financial statements, build DCF "
            "assumptions, and run a full discounted cash flow valuation with "
            "sensitivity analysis."
        )
        st.markdown("")

        ticker_input = st.text_input(
            "ticker",
            placeholder="e.g. AAPL, MSFT, GOOGL",
            label_visibility="collapsed",
        ).upper().strip()

        if st.button("Analyse →", type="primary", use_container_width=True):
            if not ticker_input:
                st.error("Please enter a ticker symbol.")
            else:
                with st.spinner(f"Fetching data for {ticker_input}…"):
                    data = _load_ticker_data(ticker_input)

                curr_price = data["fin"].get("market_data", {}).get("current_price")
                if curr_price is None:
                    st.error(
                        f"Could not find market data for **{ticker_input}**. "
                        "Check the ticker symbol and try again."
                    )
                else:
                    st.session_state.update(ticker=ticker_input, data=data, step=1)
                    st.rerun()


# ─── Step 1a: Company snapshot ─────────────────────────────────────────────

def _render_snapshot(data: dict) -> None:
    fin  = data["fin"]
    ci   = data["company_info"]
    mkt  = fin.get("market_data", {})
    pd_  = data["price_data"]
    risk = data["risk"]

    st.markdown("### Company Snapshot")

    # ── Metrics row ───────────────────────────────────────────────────
    curr_price = mkt.get("current_price")
    market_cap = mkt.get("market_cap")
    beta       = mkt.get("beta")
    score      = risk.get("overall_score")
    rlabel     = risk.get("overall_label", "")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Name",         ci["name"])
    c2.metric("Sector",       ci["sector"])
    c3.metric("Price",        _px(curr_price))
    c4.metric("Market Cap",   _bil(market_cap))
    c5.metric("Beta",         f"{beta:.2f}" if beta else "N/A")
    c6.metric("Risk Score",   f"{score:.0f}/10" if score is not None else "N/A",
                              delta=rlabel, delta_color="off")

    # ── 1-year price chart ────────────────────────────────────────────
    dates  = pd_["dates"]
    prices = pd_["prices"]
    if dates and prices:
        up          = prices[-1] >= prices[0]
        line_color  = "#16a34a" if up else "#dc2626"
        fill_color  = "rgba(22,163,74,0.07)" if up else "rgba(220,38,38,0.07)"

        fig = go.Figure(go.Scatter(
            x=dates,
            y=prices,
            mode="lines",
            line=dict(color=line_color, width=1.8),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            title="1-Year Price History",
            height=260,
            margin=dict(l=50, r=20, t=36, b=30),
            showlegend=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor="#f3f4f6", zeroline=False,
                       tickprefix="$", tickformat=",.0f"),
            font=dict(size=12),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Price history unavailable.")

    # ── Risk assessment (collapsed) ───────────────────────────────────
    with st.expander("📋 Risk Assessment", expanded=False):
        metrics = risk.get("metrics", {})
        BADGE   = {"green": "🟢", "amber": "🟡", "red": "🔴", "na": "⚪"}
        rows = [
            {
                "Metric":    m["label"],
                "Value":     m["value_str"],
                "Rating":    BADGE.get(m["rating"], "?"),
                "Note":      m["note"],
            }
            for m in metrics.values()
        ]
        if rows:
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Metric": st.column_config.TextColumn(width="medium"),
                    "Value":  st.column_config.TextColumn(width="small"),
                    "Rating": st.column_config.TextColumn(width="small"),
                    "Note":   st.column_config.TextColumn(width="large"),
                },
            )


# ─── Step 1b: Historical FCF table ─────────────────────────────────────────

def _render_fcf_table(data: dict) -> None:
    fcf    = data["fcf"]
    annual = fcf.get("annual", {})
    years  = sorted(annual.keys())

    st.markdown("### Historical Free Cash Flow")

    if not years:
        st.info("No historical FCF data available.")
        return

    rows_def = [
        ("EBIT",       "ebit",           False),
        ("D&A",        "da",             False),
        ("NWC",        "nwc",            False),
        ("ΔNWC",       "delta_nwc",      False),
        ("CapEx",      "capex",          False),
        ("FCF",        "fcf",            False),
        ("FCF/EBIT",   "fcf_ebit_ratio", True),
    ]

    table: dict[str, dict] = {}
    for label, key, is_ratio in rows_def:
        row = {}
        for yr in years:
            v = annual.get(yr, {}).get(key)
            if v is None:
                row[f"FY{yr}"] = "—"
            elif is_ratio:
                row[f"FY{yr}"] = f"{v:.2f}×"
            else:
                row[f"FY{yr}"] = _bil(v)
        table[label] = row

    df = pd.DataFrame(table).T
    df.index.name = ""

    tc   = fcf.get("effective_tax_rate")
    avg3 = fcf.get("fcf_ebit_3yr_avg")
    avg5 = fcf.get("fcf_ebit_5yr_avg")

    col_tbl, col_meta = st.columns([3, 1])
    with col_tbl:
        st.dataframe(df, use_container_width=True)
    with col_meta:
        if tc   is not None: st.metric("Effective Tax Rate", _pct(tc))
        if avg3 is not None: st.metric("FCF/EBIT  3yr avg",  _x(avg3))
        if avg5 is not None: st.metric("FCF/EBIT  5yr avg",  _x(avg5))

    if fcf.get("fcf_ebit_volatility_flag"):
        st.warning("⚠️ High FCF/EBIT volatility — FCF may be an unreliable earnings proxy.")


# ─── Step 1c: Assumptions panel ────────────────────────────────────────────

def _render_assumptions(data: dict, ticker: str) -> dict[str, Any]:
    """
    Render the editable assumptions panel.
    Returns user-selected values in decimal form (e.g. 0.0425 for 4.25%).
    Widget keys are namespaced by ticker to reset on ticker change.
    """
    assum = data["assum"]
    mkt   = data["fin"].get("market_data", {})
    k     = ticker  # key prefix

    st.markdown("### Forecast Assumptions")

    # ── Revenue growth ─────────────────────────────────────────────────
    with st.expander("📈  Revenue Growth", expanded=True):
        options: dict[str, float] = {}

        v = assum.get("revenue_cagr_3yr", {}).get("value")
        if v is not None:
            options[f"Historical 3yr CAGR  ({v:.2%})"] = v

        v = assum.get("revenue_cagr_5yr", {}).get("value")
        if v is not None:
            options[f"Historical 5yr CAGR  ({v:.2%})"] = v

        arg = assum.get("analyst_revenue_growth", {})
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
            selected = st.radio(
                "Revenue growth rate",
                list(options.keys()),
                label_visibility="collapsed",
                key=f"{k}_growth_radio",
            )
            growth_rate = options[selected]

    # ── EBIT margin + terminal growth ─────────────────────────────────
    with st.expander("📊  EBIT Margin & Terminal Growth", expanded=True):
        base_margin = assum.get("ebit_margin_avg", {}).get("value") or 0.20

        col_em, col_tg = st.columns(2)
        with col_em:
            ebit_margin_pct = st.slider(
                "EBIT Margin",
                min_value=0.0, max_value=60.0,
                value=round(base_margin * 100, 1),
                step=0.1, format="%.1f%%",
                help=f"Historical avg: {_pct(base_margin)}",
                key=f"{k}_ebit_slider",
            )
        with col_tg:
            tgr_pct = st.slider(
                "Terminal Growth Rate",
                min_value=0.5, max_value=5.0,
                value=2.5,
                step=0.1, format="%.1f%%",
                help="Gordon Growth perpetuity rate (typically 2–3%)",
                key=f"{k}_tgr_slider",
            )

    # ── WACC components ────────────────────────────────────────────────
    with st.expander("⚙️  WACC Assumptions", expanded=True):
        st.caption("Enter values as percentages (e.g. `4.25` for 4.25%). Beta is dimensionless.")

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

        # Live WACC preview
        ke_prev   = (rfr / 100) + beta * (erp / 100)
        kd_at_prev = (kd / 100) * (1 - tc / 100)
        wacc_prev  = ke_prev * (eq_w / 100) + kd_at_prev * (de_w / 100)
        st.info(
            f"**WACC preview** — "
            f"Ke = {rfr:.2f}% + {beta:.2f} × {erp:.2f}% = **{ke_prev:.2%}**  |  "
            f"Kd(AT) = {kd:.2f}% × (1−{tc:.1f}%) = **{kd_at_prev:.2%}**  |  "
            f"**WACC = {wacc_prev:.2%}**"
        )

    return {
        "growth_rate": growth_rate,
        "ebit_margin": ebit_margin_pct / 100,
        "tgr":         tgr_pct         / 100,
        "rfr":         rfr             / 100,
        "erp":         erp             / 100,
        "beta":        beta,
        "kd":          kd              / 100,
        "tc":          tc              / 100,
        "eq_w":        eq_w            / 100,
        "de_w":        de_w            / 100,
    }


# ─── Helper: patch assumptions/fin with user values ────────────────────────

def _apply_overrides(data: dict, user: dict) -> tuple[dict, dict]:
    """Return deep-copied (assumptions, financial_data) with user overrides applied."""
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


# ─── Step 2: Results ───────────────────────────────────────────────────────

def _render_results(dcf: dict, sens: dict | None) -> None:
    st.markdown("### Valuation Results")

    ud  = dcf.get("upside_downside")
    imp = dcf.get("implied_share_price")
    cur = dcf.get("current_price")

    # ── Hero: upside / downside ───────────────────────────────────────
    if ud is not None:
        sign      = "+" if ud >= 0 else ""
        direction = "▲ UPSIDE" if ud >= 0 else "▼ DOWNSIDE"
        css_cls   = "big-upside" if ud >= 0 else "big-downside"
        _, col_hero, _ = st.columns([1, 2, 1])
        with col_hero:
            st.markdown(
                f"<div class='{css_cls}'>{sign}{ud:.1%}</div>"
                f"<div class='upside-sub'>{direction} — "
                f"Implied {_px(imp)} vs Current {_px(cur)}</div>",
                unsafe_allow_html=True,
            )
    st.divider()

    # ── WACC build-up + equity bridge side by side ────────────────────
    col_wacc, col_bridge = st.columns(2)

    with col_wacc:
        st.markdown("**WACC Build-Up**")
        wb = dcf.get("wacc_buildup", {})
        df_wacc = pd.DataFrame([
            ("Risk-free Rate",         _pct(wb.get("risk_free_rate"))),
            ("Beta",                   _x(  wb.get("beta"))),
            ("Equity Risk Premium",    _pct(wb.get("equity_risk_premium"))),
            ("Cost of Equity (CAPM)",  _pct(wb.get("cost_of_equity"))),
            ("Cost of Debt (pre-tax)", _pct(wb.get("cost_of_debt_pretax"))),
            ("After-tax Cost of Debt", _pct(wb.get("after_tax_cost_of_debt"))),
            ("Equity Weight",          _pct(wb.get("equity_weight"))),
            ("Debt Weight",            _pct(wb.get("debt_weight"))),
            ("WACC",                   _pct(wb.get("wacc"))),
        ], columns=["Component", "Value"])
        st.dataframe(df_wacc, use_container_width=True, hide_index=True)

    with col_bridge:
        st.markdown("**Equity Bridge**")
        bridge = dcf.get("bridge", {})
        ev     = dcf.get("enterprise_value")
        pv_sum = dcf.get("pv_fcf_sum")
        pv_tv  = dcf.get("pv_terminal_value")
        tv_pct = (pv_tv / ev * 100) if (pv_tv and ev) else None
        shs    = bridge.get("shares_outstanding")
        shs_str = f"{shs/1e9:.2f}B shares" if shs else "N/A"
        tv_str  = _bil(pv_tv) + (f"  ({tv_pct:.0f}% of EV)" if tv_pct else "")

        df_bridge = pd.DataFrame([
            ("PV of FCFs",             _bil(pv_sum)),
            ("PV of Terminal Value",   tv_str),
            ("Enterprise Value",       _bil(ev)),
            ("(−) Total Debt",         _bil(bridge.get("total_debt"))),
            ("(+) Cash",               _bil(bridge.get("cash_and_equivalents"))),
            ("Equity Value",           _bil(bridge.get("equity_value"))),
            ("(÷) Shares Outstanding", shs_str),
            ("Implied Share Price",    _px(imp)),
            ("Current Price",          _px(cur)),
        ], columns=["Item", "Value"])
        st.dataframe(df_bridge, use_container_width=True, hide_index=True)

    st.divider()

    # ── FCF projection table ──────────────────────────────────────────
    st.markdown("**5-Year FCF Projection**")
    proj    = dcf.get("projection", {})
    inp     = dcf.get("inputs", {})
    base_yr = dcf.get("base_year")
    base_rv = dcf.get("base_revenue")
    years   = sorted(proj.keys())

    if years:
        st.caption(
            f"Revenue growth: {_pct(inp.get('revenue_growth_rate'))}  |  "
            f"EBIT margin: {_pct(inp.get('ebit_margin'))}  |  "
            f"FCF/EBIT: {_x(inp.get('fcf_ebit_ratio'))}  |  "
            f"Terminal growth: {_pct(inp.get('terminal_growth_rate'))}"
        )
        proj_cols: dict[str, list] = {
            "Metric": ["Revenue", "EBIT", "FCF", "Discount Factor", "PV of FCF"],
            f"FY{base_yr} (Base)": [_bil(base_rv), "—", "—", "—", "—"],
        }
        for yr in years:
            d = proj.get(yr, {})
            proj_cols[f"FY{yr}"] = [
                _bil(d.get("revenue")),
                _bil(d.get("ebit")),
                _bil(d.get("fcf")),
                f"{d.get('discount_factor', 0):.4f}",
                _bil(d.get("pv_fcf")),
            ]
        df_proj = pd.DataFrame(proj_cols).set_index("Metric")
        st.dataframe(df_proj, use_container_width=True)

    # ── DCF warnings ──────────────────────────────────────────────────
    warns = dcf.get("warnings", [])
    if warns:
        with st.expander(f"⚠️  {len(warns)} valuation warning(s)", expanded=False):
            for w in warns:
                st.warning(w)

    # ── Sensitivity heatmaps ──────────────────────────────────────────
    if sens:
        st.divider()
        st.markdown("**Sensitivity Analysis**")
        tab1, tab2 = st.tabs([
            "Table 1 — WACC × Terminal Growth Rate",
            "Table 2 — Revenue Growth × EBIT Margin",
        ])
        with tab1:
            t1 = sens.get("table1")
            if t1:
                _render_heatmap(t1, row_label="WACC", col_label="Terminal Growth Rate")
            else:
                st.info("Sensitivity table 1 unavailable.")
        with tab2:
            t2 = sens.get("table2")
            if t2:
                _render_heatmap(t2, row_label="Revenue Growth", col_label="EBIT Margin")
            else:
                st.info("Sensitivity table 2 unavailable.")


# ─── Sensitivity heatmap ───────────────────────────────────────────────────

def _render_heatmap(table: dict, row_label: str, col_label: str) -> None:
    """
    Render a plotly heatmap of upside/downside % for one sensitivity table.
    Base case cell is outlined in blue.  Row axis is inverted (highest value at top).
    """
    row_values = table["row_values"]
    col_values = table["col_values"]
    upsides    = table["upsides"]    # [row_idx][col_idx] → float | None
    b_row      = table["base_row_idx"]
    b_col      = table["base_col_idx"]
    n_rows     = len(row_values)

    # Build z and text arrays (row 0 = lowest row value)
    z_data, text_data = [], []
    for ri, _ in enumerate(row_values):
        z_row, t_row = [], []
        for ci, _ in enumerate(col_values):
            ud = upsides[ri][ci]
            z_row.append(ud * 100 if ud is not None else None)
            marker = "▪" if (ri == b_row and ci == b_col) else ""
            t_row.append(f"{ud:+.1%}{marker}" if ud is not None else "—")
        z_data.append(z_row)
        text_data.append(t_row)

    # Invert rows so highest row value (e.g. highest WACC) is at the top
    z_plot    = z_data[::-1]
    t_plot    = text_data[::-1]
    row_lbls  = [f"{v:.2%}" for v in reversed(row_values)]
    col_lbls  = [f"{v:.1%}" for v in col_values]

    # Base case y-index after reversal
    b_row_inv = n_rows - 1 - b_row

    flat     = [v for row in z_plot for v in row if v is not None]
    zmax     = max((abs(v) for v in flat), default=20)
    zmax     = max(zmax, 5)

    fig = go.Figure(go.Heatmap(
        z=z_plot,
        x=col_lbls,
        y=row_lbls,
        text=t_plot,
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorscale=[
            [0.00, "#b91c1c"],
            [0.30, "#fca5a5"],
            [0.50, "#f9fafb"],
            [0.70, "#86efac"],
            [1.00, "#15803d"],
        ],
        zmin=-zmax, zmid=0, zmax=zmax,
        colorbar=dict(title="Upside %", tickformat=".0f", ticksuffix="%"),
        hovertemplate=(
            f"{row_label}: %{{y}}<br>"
            f"{col_label}: %{{x}}<br>"
            "Upside: %{text}<extra></extra>"
        ),
    ))

    # Blue rectangle around base case cell (categorical axis: integer coords)
    fig.add_shape(
        type="rect",
        x0=b_col - 0.5,     x1=b_col + 0.5,
        y0=b_row_inv - 0.5, y1=b_row_inv + 0.5,
        line=dict(color="#1d4ed8", width=2.5),
        fillcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        xaxis_title=col_label,
        yaxis_title=row_label,
        height=420,
        margin=dict(l=70, r=60, t=20, b=60),
        font=dict(size=11),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Blue outline = base case  ·  {row_label} increases downward  "
        f"·  {col_label} increases right  ·  ▪ = base cell"
    )


# ─── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()
    _render_sidebar()

    step   = st.session_state.step
    ticker = st.session_state.ticker

    # Step 0 — landing
    if step == 0:
        _render_landing()
        return

    data = st.session_state.data
    if data is None:
        st.session_state.step = 0
        st.rerun()
        return

    # ── Company snapshot ──────────────────────────────────────────────
    _render_snapshot(data)
    st.divider()

    # ── Historical FCF ────────────────────────────────────────────────
    _render_fcf_table(data)
    st.divider()

    # ── Assumptions panel ─────────────────────────────────────────────
    user_vals = _render_assumptions(data, ticker)
    st.markdown("")

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        run_clicked = st.button(
            "▶  Run Valuation",
            type="primary",
            use_container_width=True,
            key="run_btn",
        )

    if run_clicked:
        assum_mod, fin_mod = _apply_overrides(data, user_vals)

        with st.spinner("Running DCF valuation…"):
            dcf = run_dcf(
                ticker_symbol=ticker,
                assumptions=assum_mod,
                fcf_result=data["fcf"],
                financial_data=fin_mod,
                revenue_growth_rate=user_vals["growth_rate"],
                terminal_growth_rate=user_vals["tgr"],
                ebit_margin_override=user_vals["ebit_margin"],
            )

        with st.spinner("Running sensitivity grids (9×8 + 9×5)…"):
            sens = build_sensitivity(
                ticker_symbol=ticker,
                base_dcf=dcf,
                assumptions=assum_mod,
                fcf_result=data["fcf"],
                financial_data=fin_mod,
            )

        st.session_state.update(dcf=dcf, sens=sens, step=2)
        st.rerun()

    # ── Results ───────────────────────────────────────────────────────
    if step >= 2 and st.session_state.dcf is not None:
        st.divider()
        _render_results(st.session_state.dcf, st.session_state.sens)


if __name__ == "__main__":
    main()
