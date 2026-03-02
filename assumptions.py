"""
assumptions.py
--------------
Builds a structured dictionary of DCF input assumptions for a US stock ticker.

Gathers the following from live market data and historical financial statements:
  1.  Risk-free rate        — live US 10-year Treasury yield (^TNX)
  2.  Market return         — annualised 10-year S&P 500 price return (^GSPC)
  3.  Equity risk premium   — default 4.50% forward-looking implied ERP; realised 10yr ERP shown for reference
  4.  Analyst rev. growth   — yfinance consensus estimates (flagged if unavailable)
  5.  Revenue CAGR 3yr/5yr  — historical CAGR from income statement
  6.  EBIT margin avg        — historical average (EBIT / Revenue)
  7.  Cost of debt          — interest_expense / total_debt (most recent year)
  8.  Effective tax rate    — average over up to 3 most recent fiscal years
  9.  Capital structure     — equity and debt weights (market cap + total debt)

Each assumption item contains at minimum:
    { "value": <float | None>, "status": "fetched" | "estimated" | "unavailable" }

Status semantics:
    "fetched"     — retrieved directly from a live yfinance API call
    "estimated"   — derived by formula from financial statement data
    "unavailable" — could not be computed; "note" key explains why

Usage
-----
    from data_fetcher import fetch_financial_data
    from assumptions import build_assumptions, print_assumptions_summary

    fin   = fetch_financial_data("AAPL")
    assum = build_assumptions("AAPL", fin)
    print_assumptions_summary(assum)
"""

import math
import statistics
from typing import Any

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float | None:
    """Convert value to float; return None for NaN / Inf / non-numeric."""
    try:
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _make(value: Any, status: str, **kwargs: Any) -> dict[str, Any]:
    """Create a standardised assumption item dict."""
    return {"value": value, "status": status, **kwargs}


def _most_recent(year_dict: dict[str, Any] | None) -> tuple[str | None, float | None]:
    """Return (year_str, value) for the most recent non-None entry."""
    if not year_dict:
        return None, None
    for yr in sorted(year_dict.keys(), reverse=True):
        v = _safe_float(year_dict[yr])
        if v is not None:
            return yr, v
    return None, None


# ---------------------------------------------------------------------------
# 1. Risk-free rate  (^TNX)
# ---------------------------------------------------------------------------

def _fetch_risk_free_rate(warnings: list[str]) -> dict[str, Any]:
    """Fetch live US 10-year Treasury yield from ^TNX (quoted in pct points)."""
    try:
        df = yf.download("^TNX", period="5d", progress=False, auto_adjust=False)
        if df.empty:
            warnings.append("^TNX download returned empty DataFrame.")
            return _make(None, "unavailable", note="^TNX returned no data")

        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        yield_pct = _safe_float(close.dropna().iloc[-1])
        if yield_pct is None:
            warnings.append("^TNX: latest Close is NaN.")
            return _make(None, "unavailable", note="^TNX latest value is NaN")

        return _make(
            yield_pct / 100.0,
            "fetched",
            source="^TNX (live)",
            note=f"Raw quote: {yield_pct:.3f}%",
        )
    except Exception as exc:
        warnings.append(f"^TNX fetch failed: {exc}")
        return _make(None, "unavailable", note=str(exc))


# ---------------------------------------------------------------------------
# 2. S&P 500 10-year annualised return  (^GSPC)
# ---------------------------------------------------------------------------

def _fetch_market_return(warnings: list[str]) -> dict[str, Any]:
    """Annualised 10-year price return of S&P 500 from ^GSPC."""
    try:
        df = yf.download("^GSPC", period="10y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 2:
            warnings.append("^GSPC download returned insufficient data.")
            return _make(None, "unavailable", note="^GSPC insufficient data")

        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = close.dropna()
        start_price = _safe_float(close.iloc[0])
        end_price   = _safe_float(close.iloc[-1])

        if not start_price or not end_price or start_price <= 0:
            warnings.append("^GSPC: invalid start/end price.")
            return _make(None, "unavailable", note="Invalid ^GSPC price data")

        start_date = close.index[0]
        end_date   = close.index[-1]
        years      = (end_date - start_date).days / 365.25
        annualized = (end_price / start_price) ** (1.0 / years) - 1.0

        return _make(
            annualized,
            "fetched",
            source="^GSPC (10-yr annualised price return)",
            note=(
                f"{start_date.date()} @ {start_price:,.0f} → "
                f"{end_date.date()} @ {end_price:,.0f}  ({years:.1f} yr)"
            ),
        )
    except Exception as exc:
        warnings.append(f"^GSPC fetch failed: {exc}")
        return _make(None, "unavailable", note=str(exc))


# ---------------------------------------------------------------------------
# 3. Equity risk premium
# ---------------------------------------------------------------------------

# Forward-looking implied ERP used as the default for WACC.
# Damodaran's implied ERP for the US market (updated annually) is ~4.5% as of
# early 2025 and has historically ranged from ~4% to ~6%.  Realised historical
# returns are a poor proxy for the forward ERP because they embed capital-gains
# windfalls from multiple expansion that are unlikely to repeat.  The 10-year
# realised S&P 500 return is still fetched and shown for transparency, but is
# labelled "reference only" and is NOT used in the WACC calculation by default.
_FORWARD_LOOKING_ERP_DEFAULT = 0.045


def _compute_erp(
    rf: dict[str, Any],
    mr: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """
    Return the equity risk premium item.

    value            = 4.50% forward-looking implied ERP (default for WACC).
    realised_erp     = market_return − risk_free_rate (for reference / display only).
    forward_looking_erp = same as value; exposed explicitly for UI overrides.
    """
    rf_val = rf.get("value")
    mr_val = mr.get("value")

    realised_erp: float | None = None
    realised_note = "Realised ERP not computed (risk-free rate or market return unavailable)."
    if rf_val is not None and mr_val is not None:
        realised_erp = mr_val - rf_val
        realised_note = (
            f"Realised 10-yr ERP: {realised_erp:.2%}  "
            f"({mr_val:.2%} S&P 500 ann. return − {rf_val:.2%} RFR)"
        )

    return {
        "value":               _FORWARD_LOOKING_ERP_DEFAULT,
        "status":              "estimated",
        "source":              "Forward-looking implied ERP (Damodaran methodology)",
        "forward_looking_erp": _FORWARD_LOOKING_ERP_DEFAULT,
        "realised_erp":        realised_erp,
        "realised_note":       realised_note,
        "note": (
            "Default 4.50% = forward-looking implied ERP for US large-cap equity. "
            "Overrideable. " + realised_note
        ),
    }


# ---------------------------------------------------------------------------
# 4. Analyst revenue growth estimates
# ---------------------------------------------------------------------------

def _fetch_analyst_revenue_growth(
    ticker_obj: yf.Ticker,
    warnings: list[str],
) -> dict[str, Any]:
    """
    Fetch analyst consensus revenue growth estimates from yfinance.

    Tries ticker.revenue_estimate for annual periods (0y = current FY, +1y = next FY).
    Returns sub-keys: current_year, next_year — each with individual status.
    Top-level status reflects whether any estimate was obtained.
    """
    items: dict[str, dict[str, Any]] = {
        "current_year": _make(None, "unavailable", note="No analyst data found"),
        "next_year":    _make(None, "unavailable", note="No analyst data found"),
    }

    # -- revenue_estimate: DataFrame indexed by period, columns include "growth"
    try:
        rev_est = ticker_obj.revenue_estimate
        if rev_est is not None and not rev_est.empty:
            growth_col = None
            for candidate in ("growth", "Growth", "revenueGrowth"):
                if candidate in rev_est.columns:
                    growth_col = candidate
                    break

            if growth_col is not None:
                for period, key in [("0y", "current_year"), ("+1y", "next_year")]:
                    if period in rev_est.index:
                        val = _safe_float(rev_est.loc[period, growth_col])
                        if val is not None:
                            items[key] = _make(
                                val, "fetched",
                                source="yfinance revenue_estimate",
                                note=f"Analyst consensus, period {period}",
                            )
            else:
                warnings.append(
                    "revenue_estimate: no 'growth' column found — "
                    f"available columns: {list(rev_est.columns)}"
                )
    except Exception as exc:
        warnings.append(f"revenue_estimate fetch failed: {exc}")

    fetched_count = sum(1 for v in items.values() if v["status"] == "fetched")
    if fetched_count == 0:
        overall_status = "unavailable"
        warnings.append(
            "[!] Analyst revenue growth estimates are UNAVAILABLE — "
            "yfinance returned no usable data. Use historical revenue CAGRs "
            "or manual input as a substitute."
        )
    elif fetched_count < len(items):
        overall_status = "fetched"
        warnings.append("Analyst revenue growth: only partial data fetched (some periods missing).")
    else:
        overall_status = "fetched"

    return {"status": overall_status, **items}


# ---------------------------------------------------------------------------
# 5. Revenue CAGR (3-year and 5-year)
# ---------------------------------------------------------------------------

def _compute_revenue_cagr(
    revenue: dict[str, Any] | None,
    warnings: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Compute 3-year and 5-year historical revenue CAGR.
    CAGR = (latest / start)^(1/n) − 1, where start is exactly n years prior.
    """
    unavail = lambda n: _make(None, "unavailable", note=f"No revenue data {n} years back")

    if not revenue:
        warnings.append("Revenue CAGR: no revenue data supplied.")
        return unavail(3), unavail(5)

    valid = {yr: v for yr, v in revenue.items() if _safe_float(v) is not None and v > 0}
    if len(valid) < 2:
        warnings.append("Revenue CAGR: fewer than 2 valid revenue data points.")
        return unavail(3), unavail(5)

    latest_yr  = max(valid.keys())
    latest_val = valid[latest_yr]

    def _cagr(n: int) -> dict[str, Any]:
        start_yr = str(int(latest_yr) - n)
        if start_yr not in valid:
            return _make(
                None, "unavailable",
                note=f"FY{start_yr} revenue not available (need {n}-yr span from FY{latest_yr})",
            )
        rate = (latest_val / valid[start_yr]) ** (1.0 / n) - 1.0
        return _make(
            rate, "estimated",
            note=f"FY{start_yr} → FY{latest_yr}  ({n} yr)",
            start_year=start_yr,
            end_year=latest_yr,
        )

    return _cagr(3), _cagr(5)


# ---------------------------------------------------------------------------
# 6. EBIT margin (historical average)
# ---------------------------------------------------------------------------

def _compute_ebit_margin(
    income_statement: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """Average EBIT / Revenue across all available years."""
    revenue = income_statement.get("revenue") or {}
    ebit    = income_statement.get("ebit")    or {}

    annual: dict[str, float] = {}
    for yr in sorted(set(revenue) & set(ebit)):
        rev_v  = _safe_float(revenue.get(yr))
        ebit_v = _safe_float(ebit.get(yr))
        if rev_v and ebit_v and rev_v != 0:
            annual[yr] = ebit_v / rev_v

    if not annual:
        warnings.append("EBIT margin: no valid (revenue, EBIT) pairs found.")
        return _make(None, "unavailable", note="No valid revenue/EBIT data")

    avg = statistics.mean(annual.values())
    yrs = sorted(annual.keys())
    return _make(
        avg, "estimated",
        note=f"Avg of FY{yrs[0]}–FY{yrs[-1]}  ({len(yrs)} yr{'s' if len(yrs)!=1 else ''})",
        annual=annual,
    )


# ---------------------------------------------------------------------------
# 7. Cost of debt
# ---------------------------------------------------------------------------

def _compute_cost_of_debt(
    income_statement: dict[str, Any],
    balance_sheet: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """abs(interest_expense) / total_debt — most recent year where both are valid."""
    interest   = income_statement.get("interest_expense") or {}
    total_debt = balance_sheet.get("total_debt")          or {}

    for yr in sorted(set(interest) & set(total_debt), reverse=True):
        ie = _safe_float(interest.get(yr))
        td = _safe_float(total_debt.get(yr))
        if ie is None or td is None or td <= 0:
            continue
        cost = abs(ie) / td
        if 0.0 < cost < 1.0:           # sanity: 0–100%
            return _make(
                cost, "estimated",
                note=f"abs(interest_expense) / total_debt, FY{yr}",
                year=yr,
            )
        warnings.append(
            f"Cost of debt FY{yr}: implausible value {cost:.1%} — skipped."
        )

    warnings.append(
        "Cost of debt: no valid interest_expense / total_debt pair found. "
        "Interest expense may not be reported separately for this ticker."
    )
    return _make(None, "unavailable", note="No valid interest_expense/total_debt pair")


# ---------------------------------------------------------------------------
# 8. Effective tax rate (3-year average)
# ---------------------------------------------------------------------------

def _compute_effective_tax_rate(
    income_statement: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """Average effective tax rate (tax_expense / pretax_income) over ≤3 recent years."""
    tax    = income_statement.get("tax_expense")   or {}
    pretax = income_statement.get("pretax_income") or {}

    rates: dict[str, float] = {}
    for yr in sorted(set(tax) & set(pretax), reverse=True)[:3]:
        t = _safe_float(tax.get(yr))
        p = _safe_float(pretax.get(yr))
        if t is None or p is None or p <= 0:
            continue
        rate = t / p
        if 0.0 <= rate <= 1.0:
            rates[yr] = rate
        else:
            warnings.append(
                f"Tax rate FY{yr}: implausible value {rate:.1%} — excluded from average."
            )

    if not rates:
        warnings.append("Effective tax rate: no valid tax/pretax pairs found.")
        return _make(None, "unavailable", note="No valid tax/pretax income pairs")

    avg = statistics.mean(rates.values())
    yrs = sorted(rates.keys())
    return _make(
        avg, "estimated",
        note=f"Avg of FY{yrs[0]}–FY{yrs[-1]}  ({len(yrs)} yr{'s' if len(yrs)!=1 else ''})",
        annual_rates=rates,
    )


# ---------------------------------------------------------------------------
# 9. Capital structure weights
# ---------------------------------------------------------------------------

def _compute_capital_structure(
    balance_sheet: dict[str, Any],
    market_data: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """
    Equity and debt weights derived from market cap and most-recent total debt.
      equity_weight = market_cap / (market_cap + total_debt)
      debt_weight   = total_debt / (market_cap + total_debt)
    """
    market_cap = _safe_float(market_data.get("market_cap"))
    td_yr, total_debt = _most_recent(balance_sheet.get("total_debt"))

    if market_cap is None:
        warnings.append("Capital structure: market_cap unavailable.")
    if total_debt is None:
        warnings.append("Capital structure: total_debt unavailable — treating as 0.")
        total_debt = 0.0

    if market_cap is None:
        return _make(None, "unavailable", note="market_cap unavailable")

    total = market_cap + total_debt
    if total <= 0:
        warnings.append("Capital structure: total market value ≤ 0.")
        return _make(None, "unavailable", note="Total market value ≤ 0")

    return {
        "equity_weight": market_cap / total,
        "debt_weight":   total_debt / total,
        "market_cap":    market_cap,
        "total_debt":    total_debt,
        "total_debt_year": td_yr,
        "status":  "estimated",
        "note":    (
            f"Market cap / (market cap + total debt FY{td_yr})"
            if td_yr else "Market cap / (market cap + total debt)"
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_assumptions(
    ticker_symbol: str,
    financial_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Compile a full set of DCF input assumptions for a ticker.

    Parameters
    ----------
    ticker_symbol  : str   — US stock ticker, e.g. "AAPL"
    financial_data : dict  — output of data_fetcher.fetch_financial_data()

    Returns
    -------
    dict with keys:
        ticker, risk_free_rate, market_return, equity_risk_premium,
        analyst_revenue_growth, revenue_cagr_3yr, revenue_cagr_5yr,
        ebit_margin_avg, cost_of_debt, effective_tax_rate,
        capital_structure, warnings
    """
    ticker_symbol = ticker_symbol.upper().strip()
    warnings: list[str] = []

    inc = financial_data.get("income_statement", {})
    bal = financial_data.get("balance_sheet",    {})
    mkt = financial_data.get("market_data",      {})

    ticker_obj = yf.Ticker(ticker_symbol)

    # 1–2. Live market data
    risk_free_rate = _fetch_risk_free_rate(warnings)
    market_return  = _fetch_market_return(warnings)

    # 3. ERP
    equity_risk_premium = _compute_erp(risk_free_rate, market_return, warnings)

    # 4. Analyst estimates
    analyst_revenue_growth = _fetch_analyst_revenue_growth(ticker_obj, warnings)

    # 5. Revenue CAGRs
    revenue_cagr_3yr, revenue_cagr_5yr = _compute_revenue_cagr(
        inc.get("revenue"), warnings
    )

    # 6–9. Income-statement / balance-sheet derived
    ebit_margin_avg    = _compute_ebit_margin(inc, warnings)
    cost_of_debt       = _compute_cost_of_debt(inc, bal, warnings)
    effective_tax_rate = _compute_effective_tax_rate(inc, warnings)
    capital_structure  = _compute_capital_structure(bal, mkt, warnings)

    return {
        "ticker":                 ticker_symbol,
        "risk_free_rate":         risk_free_rate,
        "market_return":          market_return,
        "equity_risk_premium":    equity_risk_premium,
        "analyst_revenue_growth": analyst_revenue_growth,
        "revenue_cagr_3yr":       revenue_cagr_3yr,
        "revenue_cagr_5yr":       revenue_cagr_5yr,
        "ebit_margin_avg":        ebit_margin_avg,
        "cost_of_debt":           cost_of_debt,
        "effective_tax_rate":     effective_tax_rate,
        "capital_structure":      capital_structure,
        "warnings":               warnings,
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

_STATUS_BADGE: dict[str, str] = {
    "fetched":     "[FETCHED]    ",
    "estimated":   "[ESTIMATED]  ",
    "unavailable": "[UNAVAILABLE]",
}


def _badge(status: str) -> str:
    return _STATUS_BADGE.get(status, f"[{status.upper():<11}]")


def _pct(value: float | None, dp: int = 2) -> str:
    if value is None:
        return "     N/A"
    return f"{value:>{7+dp}.{dp}%}"


def _bil(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1e12:
        return f"${value/1e12:.2f}T"
    if abs(value) >= 1e9:
        return f"${value/1e9:.1f}B"
    if abs(value) >= 1e6:
        return f"${value/1e6:.1f}M"
    return f"${value:,.0f}"


def _row(label: str, badge: str, value_str: str, note: str = "") -> str:
    note_part = f"  {note}" if note else ""
    return f"  {label:<32} {badge}  {value_str}{note_part}"


def print_assumptions_summary(result: dict[str, Any]) -> None:
    """Print a human-readable summary of build_assumptions() output."""
    ticker = result.get("ticker", "?")
    W = 72
    sep  = "─" * W
    dsep = "═" * W

    print(f"\n{dsep}")
    print(f"  DCF Assumptions — {ticker}")
    print(dsep)

    # ── Market data ──────────────────────────────────────────────────────
    print(f"\n  {'MARKET DATA':}")
    print(f"  {sep}")

    rf = result["risk_free_rate"]
    print(_row("Risk-free rate (10yr Treasury)",
               _badge(rf["status"]),
               _pct(rf["value"]),
               rf.get("note", "")))

    mr = result["market_return"]
    print(_row("S&P 500 10-yr ann. return",
               _badge(mr["status"]),
               _pct(mr["value"]),
               mr.get("note", "")))

    erp          = result["equity_risk_premium"]
    fwd_erp      = erp.get("forward_looking_erp", erp.get("value"))
    realised_erp = erp.get("realised_erp")

    print(_row("ERP — forward-looking (default)",
               _badge(erp["status"]),
               _pct(fwd_erp),
               "Used in WACC  |  overrideable"))
    if realised_erp is not None:
        print(_row("ERP — realised 10yr S&P 500",
                   _badge("fetched"),
                   _pct(realised_erp),
                   "Reference only  |  NOT used in WACC"))
    mr_val = result.get("market_return", {}).get("value")
    if realised_erp is not None and mr_val is not None:
        print(f"    {'':32}  "
              f"[Note] Realised ERP ({realised_erp:.2%}) reflects the exceptional 2016–2026")
        print(f"    {'':32}         S&P 500 bull run ({mr_val:.2%} ann.). Using it as a")
        print(f"    {'':32}         forward discount rate would overstate WACC and")
        print(f"    {'':32}         undervalue most equities. The 4.50% forward-looking")
        print(f"    {'':32}         implied ERP is what the market currently prices in.")

    # ── Growth estimates ─────────────────────────────────────────────────
    print(f"\n  {'GROWTH ESTIMATES':}")
    print(f"  {sep}")

    arg = result["analyst_revenue_growth"]
    for sub_key, label in [("current_year", "Analyst rev. growth (cur. FY)"),
                            ("next_year",    "Analyst rev. growth (next FY)")]:
        item = arg.get(sub_key, {})
        note = item.get("note", "")
        if item["status"] == "unavailable":
            note = "[!] " + note
        print(_row(label, _badge(item["status"]), _pct(item.get("value")), note))

    cagr3 = result["revenue_cagr_3yr"]
    print(_row("Revenue CAGR  3-year",
               _badge(cagr3["status"]),
               _pct(cagr3["value"]),
               cagr3.get("note", "")))

    cagr5 = result["revenue_cagr_5yr"]
    print(_row("Revenue CAGR  5-year",
               _badge(cagr5["status"]),
               _pct(cagr5["value"]),
               cagr5.get("note", "")))

    # ── Profitability ─────────────────────────────────────────────────────
    print(f"\n  {'PROFITABILITY':}")
    print(f"  {sep}")

    em = result["ebit_margin_avg"]
    print(_row("Avg EBIT margin",
               _badge(em["status"]),
               _pct(em["value"]),
               em.get("note", "")))

    if em.get("annual"):
        annual_parts = "  ".join(
            f"{yr}: {v:.1%}" for yr, v in sorted(em["annual"].items())
        )
        print(f"    {'':32}  {annual_parts}")

    # ── Cost of capital ───────────────────────────────────────────────────
    print(f"\n  {'COST OF CAPITAL':}")
    print(f"  {sep}")

    cod = result["cost_of_debt"]
    print(_row("Cost of debt",
               _badge(cod["status"]),
               _pct(cod["value"]),
               cod.get("note", "")))

    etr = result["effective_tax_rate"]
    print(_row("Effective tax rate",
               _badge(etr["status"]),
               _pct(etr["value"]),
               etr.get("note", "")))

    # ── Capital structure ─────────────────────────────────────────────────
    print(f"\n  {'CAPITAL STRUCTURE':}")
    print(f"  {sep}")

    cs = result["capital_structure"]
    cs_status = cs.get("status", "unavailable")
    eq_w  = cs.get("equity_weight")
    de_w  = cs.get("debt_weight")
    mcap  = cs.get("market_cap")
    tdebt = cs.get("total_debt")

    print(_row("Equity weight",
               _badge(cs_status),
               _pct(eq_w),
               f"Market cap {_bil(mcap)}" if mcap else ""))
    print(_row("Debt weight",
               _badge(cs_status),
               _pct(de_w),
               f"Total debt {_bil(tdebt)}" + (f" (FY{cs['total_debt_year']})" if cs.get("total_debt_year") else "") if tdebt else ""))

    # ── Warnings ──────────────────────────────────────────────────────────
    all_warnings = result.get("warnings", [])
    if all_warnings:
        print(f"\n  Warnings ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"    [!] {w}")
    else:
        print("\n  No warnings.")

    print(f"\n{dsep}\n")


# ---------------------------------------------------------------------------
# Entry point — test with AAPL
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pprint
    from data_fetcher import fetch_financial_data

    print("Fetching AAPL financial data...")
    fin_data = fetch_financial_data("AAPL")

    if fin_data.get("warnings"):
        print(f"  data_fetcher warnings: {len(fin_data['warnings'])}")

    print("Building assumptions...")
    assum = build_assumptions("AAPL", fin_data)

    print_assumptions_summary(assum)

    print("Raw assumptions dictionary:")
    pprint.pprint(assum, width=110, sort_dicts=False)
