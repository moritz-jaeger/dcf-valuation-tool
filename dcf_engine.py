"""
dcf_engine.py
-------------
Runs a discounted cash flow (DCF) valuation for a US stock ticker.

Inputs
------
  assumptions        — dict from assumptions.build_assumptions()
  fcf_result         — dict from fcf_calculator.calculate_fcf()
  financial_data     — dict from data_fetcher.fetch_financial_data()
  revenue_growth_rate  — forward annual revenue growth rate (e.g. 0.065)
  terminal_growth_rate — Gordon Growth perpetuity rate    (e.g. 0.025)
  projection_years     — forecast horizon (default 5)

Valuation steps
---------------
  1.  Revenue projection  : Rev(t) = Rev(t−1) × (1 + g)
  2.  EBIT projection     : EBIT(t) = Rev(t) × ebit_margin
  3.  FCF projection      : FCF(t)  = EBIT(t) × fcf_ebit_ratio
  4.  WACC build-up (CAPM):
        Cost of equity    = RFR + β × ERP
        After-tax Kd      = cost_of_debt × (1 − tax_rate)
        WACC              = Ke × equity_weight + Kd_at × debt_weight
  5.  Discount FCFs       : PV(t) = FCF(t) / (1 + WACC)^t
  6.  Terminal value      : TV = FCF_N × (1 + tgr) / (WACC − tgr)
  7.  PV of TV            : PV_TV = TV / (1 + WACC)^N
  8.  Enterprise value    : EV = Σ PV(FCF) + PV_TV
  9.  Bridge to equity    : Equity = EV − total_debt + cash
  10. Implied price       : Price  = Equity / shares_outstanding
  11. Upside / downside   : (implied_price / current_price) − 1
"""

import math
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(value: Any) -> float | None:
    """Return float, or None for NaN / Inf / non-numeric."""
    try:
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _most_recent(year_dict: dict | None) -> tuple[str | None, float | None]:
    """(year_str, value) for the most recent non-None entry in a year-keyed dict."""
    if not year_dict:
        return None, None
    for yr in sorted(year_dict.keys(), reverse=True):
        v = _safe(year_dict[yr])
        if v is not None:
            return yr, v
    return None, None


def _warn(value: float | None, name: str, warnings: list[str]) -> float | None:
    """Append a warning if value is None; return value unchanged."""
    if value is None:
        warnings.append(f"Required input '{name}' is missing — result may be incomplete.")
    return value


# ---------------------------------------------------------------------------
# WACC build-up
# ---------------------------------------------------------------------------

def _build_wacc(
    assumptions: dict[str, Any],
    financial_data: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """
    Compute WACC via CAPM for the cost of equity.

    Returns a dict containing every intermediate component.
    """
    rfr   = _safe(assumptions.get("risk_free_rate",       {}).get("value"))
    erp   = _safe(assumptions.get("equity_risk_premium",  {}).get("value"))
    kd    = _safe(assumptions.get("cost_of_debt",         {}).get("value"))
    tc    = _safe(assumptions.get("effective_tax_rate",   {}).get("value"))
    eq_w  = _safe(assumptions.get("capital_structure",    {}).get("equity_weight"))
    de_w  = _safe(assumptions.get("capital_structure",    {}).get("debt_weight"))
    beta  = _safe(financial_data.get("market_data",       {}).get("beta"))

    for val, name in [
        (rfr,  "risk_free_rate"),
        (erp,  "equity_risk_premium"),
        (kd,   "cost_of_debt"),
        (tc,   "effective_tax_rate"),
        (eq_w, "equity_weight"),
        (de_w, "debt_weight"),
    ]:
        _warn(val, name, warnings)

    if beta is None:
        warnings.append("Beta not available — defaulting to 1.0 for CAPM.")
        beta = 1.0

    ke    = (rfr + beta * erp)   if (rfr is not None and erp is not None) else None
    kd_at = (kd * (1.0 - tc))   if (kd  is not None and tc  is not None) else None
    wacc  = (
        ke * eq_w + kd_at * de_w
        if (ke is not None and kd_at is not None and eq_w is not None and de_w is not None)
        else None
    )

    if wacc is not None and not (0.01 <= wacc <= 0.50):
        warnings.append(
            f"WACC {wacc:.2%} is outside the typical 1%–50% range — "
            "check input assumptions."
        )

    return {
        "risk_free_rate":         rfr,
        "beta":                   beta,
        "equity_risk_premium":    erp,
        "cost_of_equity":         ke,
        "cost_of_debt_pretax":    kd,
        "tax_rate":               tc,
        "after_tax_cost_of_debt": kd_at,
        "equity_weight":          eq_w,
        "debt_weight":            de_w,
        "wacc":                   wacc,
    }


# ---------------------------------------------------------------------------
# Revenue / FCF projection
# ---------------------------------------------------------------------------

def _project(
    base_revenue: float,
    base_year: str,
    revenue_growth_rate: float,
    ebit_margin: float,
    fcf_ebit_ratio: float,
    wacc: float,
    terminal_growth_rate: float,
    projection_years: int,
    warnings: list[str],
) -> dict[str, Any]:
    """
    Build the N-year FCF projection and Gordon Growth terminal value.

    Returns dict with keys:
        annual           — year-keyed projection rows
        pv_fcf_sum       — sum of discounted FCFs
        terminal_value   — Gordon Growth TV (at end of projection)
        pv_terminal_value — TV discounted to today
        terminal_fcf     — FCF in final projection year (basis for TV)
    """
    annual: dict[str, dict[str, float | None]] = {}
    pv_fcf_sum = 0.0
    rev = base_revenue

    for t in range(1, projection_years + 1):
        yr   = str(int(base_year) + t)
        rev  = rev * (1.0 + revenue_growth_rate)
        ebit = rev * ebit_margin
        fcf  = ebit * fcf_ebit_ratio
        df   = 1.0 / (1.0 + wacc) ** t
        pv   = fcf * df
        pv_fcf_sum += pv

        annual[yr] = {
            "year_index":      t,
            "revenue":         rev,
            "ebit":            ebit,
            "fcf":             fcf,
            "discount_factor": df,
            "pv_fcf":          pv,
        }

    # Terminal value — Gordon Growth on year-N FCF grown one more period
    terminal_fcf = rev * ebit_margin * fcf_ebit_ratio  # FCF in year N

    if wacc <= terminal_growth_rate:
        warnings.append(
            f"WACC ({wacc:.2%}) ≤ terminal growth rate ({terminal_growth_rate:.2%}) — "
            "Gordon Growth model undefined. Terminal value set to None."
        )
        tv = pv_tv = None
    else:
        tv    = terminal_fcf * (1.0 + terminal_growth_rate) / (wacc - terminal_growth_rate)
        pv_tv = tv / (1.0 + wacc) ** projection_years

    return {
        "annual":             annual,
        "pv_fcf_sum":         pv_fcf_sum,
        "terminal_value":     tv,
        "pv_terminal_value":  pv_tv,
        "terminal_fcf":       terminal_fcf,
    }


# ---------------------------------------------------------------------------
# Enterprise-value → equity bridge
# ---------------------------------------------------------------------------

def _equity_bridge(
    enterprise_value: float | None,
    financial_data: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """
    Bridge from Enterprise Value to implied share price.

        Equity value  = EV − total_debt + cash_and_equivalents
        Implied price = Equity value / shares_outstanding
    """
    bal = financial_data.get("balance_sheet", {})
    mkt = financial_data.get("market_data",   {})

    td_yr, total_debt = _most_recent(bal.get("total_debt"))
    _,     cash       = _most_recent(bal.get("cash_and_equivalents"))
    shares            = _safe(mkt.get("shares_outstanding"))
    curr_price        = _safe(mkt.get("current_price"))

    if total_debt is None:
        warnings.append("total_debt unavailable — treating as 0 in equity bridge.")
        total_debt = 0.0
    if cash is None:
        warnings.append("cash_and_equivalents unavailable — treating as 0 in equity bridge.")
        cash = 0.0
    if shares is None:
        warnings.append("shares_outstanding unavailable — implied price cannot be computed.")

    net_debt      = total_debt - cash
    equity_value  = (enterprise_value - net_debt) if enterprise_value is not None else None
    implied_price = (equity_value / shares)        if (equity_value is not None and shares) else None
    upside        = ((implied_price / curr_price) - 1.0) if (implied_price and curr_price) else None

    return {
        "total_debt":           total_debt,
        "total_debt_year":      td_yr,
        "cash_and_equivalents": cash,
        "net_debt":             net_debt,
        "equity_value":         equity_value,
        "shares_outstanding":   shares,
        "implied_share_price":  implied_price,
        "current_price":        curr_price,
        "upside_downside":      upside,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_dcf(
    ticker_symbol: str,
    assumptions: dict[str, Any],
    fcf_result: dict[str, Any],
    financial_data: dict[str, Any],
    revenue_growth_rate: float,
    terminal_growth_rate: float,
    projection_years: int = 5,
    fcf_ebit_override: float | None = None,
    ebit_margin_override: float | None = None,
    wacc_override: float | None = None,
) -> dict[str, Any]:
    """
    Run a DCF valuation for a stock ticker.

    Parameters
    ----------
    ticker_symbol        : str   — e.g. "AAPL"
    assumptions          : dict  — from assumptions.build_assumptions()
    fcf_result           : dict  — from fcf_calculator.calculate_fcf()
    financial_data       : dict  — from data_fetcher.fetch_financial_data()
    revenue_growth_rate  : float — forward annual revenue growth (e.g. 0.065)
    terminal_growth_rate : float — Gordon Growth terminal rate   (e.g. 0.025)
    projection_years     : int   — forecast horizon, default 5
    fcf_ebit_override    : float | None — bypass FCF/EBIT ratio from history
    ebit_margin_override : float | None — bypass EBIT margin from history
    wacc_override        : float | None — bypass CAPM WACC (used for sensitivity)

    Returns
    -------
    dict with keys:
        ticker, inputs, wacc_buildup, base_year, base_revenue,
        projection, pv_fcf_sum, terminal_value, pv_terminal_value,
        terminal_fcf, enterprise_value, bridge,
        implied_share_price, current_price, upside_downside, warnings
    """
    ticker_symbol = ticker_symbol.upper().strip()
    warnings: list[str] = []

    # ── WACC ─────────────────────────────────────────────────────────
    wacc_buildup = _build_wacc(assumptions, financial_data, warnings)
    if wacc_override is not None:
        wacc = wacc_override
        wacc_buildup["wacc"] = wacc_override   # keep buildup dict consistent
    else:
        wacc = wacc_buildup["wacc"]
    if wacc is None:
        warnings.append("WACC could not be computed — DCF cannot proceed.")
        return _empty_result(ticker_symbol, warnings)

    # ── EBIT margin ───────────────────────────────────────────────────
    ebit_margin = (
        ebit_margin_override
        if ebit_margin_override is not None
        else _safe(assumptions.get("ebit_margin_avg", {}).get("value"))
    )
    if ebit_margin is None:
        warnings.append("EBIT margin unavailable — DCF cannot proceed.")
        return _empty_result(ticker_symbol, warnings)

    # ── FCF / EBIT ratio (prefer 3yr, fallback 5yr) ──────────────────
    if fcf_ebit_override is not None:
        fcf_ebit_ratio = fcf_ebit_override
    else:
        fcf_ebit_ratio = _safe(fcf_result.get("fcf_ebit_3yr_avg"))
        if fcf_ebit_ratio is None:
            fcf_ebit_ratio = _safe(fcf_result.get("fcf_ebit_5yr_avg"))
            if fcf_ebit_ratio is not None:
                warnings.append("FCF/EBIT 3yr avg unavailable — using 5yr avg instead.")
    if fcf_ebit_ratio is None:
        warnings.append("FCF/EBIT ratio unavailable — DCF cannot proceed.")
        return _empty_result(ticker_symbol, warnings)

    # ── Base revenue (most recent fiscal year) ────────────────────────
    inc = financial_data.get("income_statement", {})
    base_yr, base_rev = _most_recent(inc.get("revenue"))
    if base_rev is None:
        warnings.append("Base revenue unavailable — DCF cannot proceed.")
        return _empty_result(ticker_symbol, warnings)

    # Sanity-check growth rate
    if abs(revenue_growth_rate) > 0.50:
        warnings.append(
            f"Revenue growth rate {revenue_growth_rate:.1%} is unusually "
            "large (>50%) — verify input."
        )

    # ── Projection ────────────────────────────────────────────────────
    proj = _project(
        base_revenue=base_rev,
        base_year=base_yr,
        revenue_growth_rate=revenue_growth_rate,
        ebit_margin=ebit_margin,
        fcf_ebit_ratio=fcf_ebit_ratio,
        wacc=wacc,
        terminal_growth_rate=terminal_growth_rate,
        projection_years=projection_years,
        warnings=warnings,
    )

    # ── Enterprise value ──────────────────────────────────────────────
    pv_tv = proj["pv_terminal_value"]
    ev    = (proj["pv_fcf_sum"] + pv_tv) if pv_tv is not None else None

    # ── Bridge to equity ──────────────────────────────────────────────
    bridge = _equity_bridge(ev, financial_data, warnings)

    return {
        "ticker":              ticker_symbol,
        "inputs": {
            "revenue_growth_rate":  revenue_growth_rate,
            "terminal_growth_rate": terminal_growth_rate,
            "projection_years":     projection_years,
            "ebit_margin":          ebit_margin,
            "fcf_ebit_ratio":       fcf_ebit_ratio,
            "wacc":                 wacc,
        },
        "wacc_buildup":        wacc_buildup,
        "base_year":           base_yr,
        "base_revenue":        base_rev,
        "projection":          proj["annual"],
        "pv_fcf_sum":          proj["pv_fcf_sum"],
        "terminal_value":      proj["terminal_value"],
        "pv_terminal_value":   pv_tv,
        "terminal_fcf":        proj["terminal_fcf"],
        "enterprise_value":    ev,
        "bridge":              bridge,
        "implied_share_price": bridge["implied_share_price"],
        "current_price":       bridge["current_price"],
        "upside_downside":     bridge["upside_downside"],
        "warnings":            warnings,
    }


def _empty_result(ticker: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "ticker":              ticker,
        "inputs":              {},
        "wacc_buildup":        {},
        "base_year":           None,
        "base_revenue":        None,
        "projection":          {},
        "pv_fcf_sum":          None,
        "terminal_value":      None,
        "pv_terminal_value":   None,
        "terminal_fcf":        None,
        "enterprise_value":    None,
        "bridge":              {},
        "implied_share_price": None,
        "current_price":       None,
        "upside_downside":     None,
        "warnings":            warnings,
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def _pct(v: float | None, dp: int = 2, sign: bool = False) -> str:
    if v is None:
        return "N/A"
    s = f"{v:+.{dp}%}" if sign else f"{v:.{dp}%}"
    return s


def _bil(v: float | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v/1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    return f"${v:,.0f}"


def _x(v: float | None) -> str:
    return "N/A" if v is None else f"{v:.2f}x"


def _px(v: float | None) -> str:
    return "N/A" if v is None else f"${v:,.2f}"


def _df(v: float | None) -> str:
    return "N/A" if v is None else f"{v:.4f}"


def print_dcf_summary(result: dict[str, Any]) -> None:
    """Print a formatted DCF valuation summary."""
    ticker = result.get("ticker", "?")
    wb     = result.get("wacc_buildup", {})
    inp    = result.get("inputs", {})
    proj   = result.get("projection", {})
    bridge = result.get("bridge", {})
    years  = sorted(proj.keys())

    g   = inp.get("revenue_growth_rate")
    tgr = inp.get("terminal_growth_rate")

    # Dynamic table width
    LABEL = 22
    COL   = 11
    n_cols = 1 + len(years)          # base column + forecast years
    TW = LABEL + COL * n_cols        # total table width
    W  = max(TW, 72)
    dsep = "═" * W
    sep  = "─" * W

    print(f"\n{dsep}")
    print(f"  DCF Valuation — {ticker}")
    notes = []
    if g   is not None: notes.append(f"Revenue growth: {_pct(g)}")
    if tgr is not None: notes.append(f"Terminal growth: {_pct(tgr)}")
    if notes:
        print(f"  {('  |  ').join(notes)}")
    print(dsep)

    # ── WACC build-up ────────────────────────────────────────────────
    print(f"\n  WACC BUILD-UP")
    print(f"  {sep}")

    rfr   = wb.get("risk_free_rate")
    beta  = wb.get("beta")
    erp   = wb.get("equity_risk_premium")
    ke    = wb.get("cost_of_equity")
    kd    = wb.get("cost_of_debt_pretax")
    tc    = wb.get("tax_rate")
    kd_at = wb.get("after_tax_cost_of_debt")
    eq_w  = wb.get("equity_weight")
    de_w  = wb.get("debt_weight")
    wacc  = wb.get("wacc")

    RL, VL = 38, 9   # row label width, value width

    def _wrow(label: str, val: str, note: str = "") -> None:
        note_str = f"  ({note})" if note else ""
        print(f"  {label:<{RL}} {val:>{VL}}{note_str}")

    _wrow("Risk-free rate",          _pct(rfr))
    _wrow("Beta",                    _x(beta))
    _wrow("Equity risk premium",     _pct(erp))
    capm_note = (f"{_pct(rfr)} + {_x(beta)} × {_pct(erp)}"
                 if all(v is not None for v in [rfr, beta, erp]) else "")
    _wrow("Cost of equity  (CAPM)",  _pct(ke),    capm_note)
    print(f"  {'':>{RL}}")
    kdat_note = (f"{_pct(kd)} × (1 − {_pct(tc)})"
                 if all(v is not None for v in [kd, tc]) else "")
    _wrow("Cost of debt (pre-tax)",  _pct(kd))
    _wrow("After-tax cost of debt",  _pct(kd_at), kdat_note)
    _wrow("Equity weight",           _pct(eq_w))
    _wrow("Debt weight",             _pct(de_w))
    print(f"  {sep}")
    _wrow("WACC",                    _pct(wacc))

    # ── 5-year projection table ──────────────────────────────────────
    base_yr  = result.get("base_year", "Base")
    base_rev = result.get("base_revenue")
    em  = inp.get("ebit_margin")
    fer = inp.get("fcf_ebit_ratio")

    print(f"\n  {len(years)}-YEAR FCF PROJECTION")
    margin_note = (
        f"  EBIT margin {_pct(em, dp=1)}  ×  FCF/EBIT ratio {_x(fer)}"
        if em and fer else ""
    )
    print(f"{margin_note}")
    print(f"  {sep}")

    header = f"  {'':>{LABEL-2}}" + f"{'Base (FY'+base_yr+')':>{COL}}" + "".join(
        f"{yr:>{COL}}" for yr in years
    )
    print(header)
    print(f"  {sep}")

    def _prow(label: str, base_val: Any, field: str, fmt) -> None:
        row = f"  {label:<{LABEL-2}}" + f"{fmt(base_val):>{COL}}"
        for yr in years:
            row += f"{fmt(proj.get(yr, {}).get(field)):>{COL}}"
        print(row)

    _prow("Revenue",         base_rev, "revenue",         _bil)
    _prow("EBIT",            None,     "ebit",            _bil)
    _prow("FCF",             None,     "fcf",             _bil)
    _prow("Discount factor", None,     "discount_factor", _df)
    _prow("PV of FCF",       None,     "pv_fcf",          _bil)

    print(f"  {sep}")

    pv_sum = result.get("pv_fcf_sum")
    tv     = result.get("terminal_value")
    pv_tv  = result.get("pv_terminal_value")
    ev     = result.get("enterprise_value")

    SL, SV = 36, 13   # summary label/value widths

    def _srow(label: str, val: str, indent: int = 0) -> None:
        pad = "  " * indent
        print(f"  {pad}{label:<{SL - 2*indent}} {val:>{SV}}")

    _srow("Sum of PV(FCFs)",      _bil(pv_sum))
    _srow("Terminal value",       _bil(tv))
    _srow("PV of terminal value", _bil(pv_tv))
    if pv_tv is not None and ev:
        _srow("TV as % of EV", _pct(pv_tv / ev), indent=1)
    print(f"  {sep}")
    _srow("Enterprise value",     _bil(ev))

    # ── Equity bridge ────────────────────────────────────────────────
    td   = bridge.get("total_debt")
    td_yr = bridge.get("total_debt_year")
    cash = bridge.get("cash_and_equivalents")
    eqv  = bridge.get("equity_value")
    shs  = bridge.get("shares_outstanding")
    imp  = bridge.get("implied_share_price")
    cur  = bridge.get("current_price")
    ud   = bridge.get("upside_downside")

    print(f"\n  EQUITY BRIDGE")
    print(f"  {sep}")
    _srow("Enterprise value",                   _bil(ev))
    _srow(f"(−) Total debt  (FY{td_yr or '?'})", _bil(td),   indent=1)
    _srow("(+) Cash & equivalents",             _bil(cash), indent=1)
    print(f"  {sep}")
    _srow("Equity value",                        _bil(eqv))
    shs_str = f"{shs/1e9:.2f}B shares" if shs else "N/A"
    _srow("(÷) Shares outstanding",             shs_str,   indent=1)
    print(f"  {sep}")
    _srow("Implied share price",                 _px(imp))
    _srow("Current price",                       _px(cur))

    if ud is not None:
        sign   = "+" if ud >= 0 else ""
        arrow  = "▲ UPSIDE" if ud >= 0 else "▼ DOWNSIDE"
        print(f"\n  {'Upside / downside':<{SL}} {sign}{ud:.1%}  {arrow}")

    # ── Warnings ─────────────────────────────────────────────────────
    warns = result.get("warnings", [])
    if warns:
        print(f"\n  Warnings ({len(warns)}):")
        for w in warns:
            print(f"    [!] {w}")

    print(f"\n{dsep}\n")


# ---------------------------------------------------------------------------
# Entry point — test on AAPL
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pprint
    from data_fetcher   import fetch_financial_data
    from fcf_calculator import calculate_fcf
    from assumptions    import build_assumptions

    TICKER          = "AAPL"
    TERMINAL_GROWTH = 0.025

    print(f"[1/3] Fetching {TICKER} financial data...")
    fin = fetch_financial_data(TICKER)

    print(f"[2/3] Calculating FCF...")
    fcf_res = calculate_fcf(fin)

    print(f"[3/3] Building assumptions...")
    assum = build_assumptions(TICKER, fin)

    # Select revenue growth: analyst next-year → current-year → 3yr CAGR
    arg = assum.get("analyst_revenue_growth", {})
    growth_candidates = [
        (arg.get("next_year",    {}).get("value"), "analyst next-year estimate"),
        (arg.get("current_year", {}).get("value"), "analyst current-year estimate"),
        (assum.get("revenue_cagr_3yr", {}).get("value"), "historical 3-year CAGR"),
    ]
    growth_rate, growth_source = next(
        ((v, s) for v, s in growth_candidates if v is not None),
        (None, "none"),
    )

    if growth_rate is None:
        print("ERROR: No revenue growth rate available — aborting.")
        raise SystemExit(1)

    print(f"\n  Growth rate : {growth_rate:.2%}  ({growth_source})")
    print(f"  Terminal g  : {TERMINAL_GROWTH:.2%}\n")

    dcf = run_dcf(
        ticker_symbol=TICKER,
        assumptions=assum,
        fcf_result=fcf_res,
        financial_data=fin,
        revenue_growth_rate=growth_rate,
        terminal_growth_rate=TERMINAL_GROWTH,
    )

    print_dcf_summary(dcf)

    print("Raw DCF result dictionary:")
    pprint.pprint(dcf, width=110, sort_dicts=False)
