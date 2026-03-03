"""
fcf_calculator.py
-----------------
Calculates historical Free Cash Flow (FCF) from the output of data_fetcher.py.

Formula:
    FCF = EBIT × (1 − tc) + D&A − ΔNWC − CapEx

Where:
    NWC  = (Current Assets − Cash & Equivalents) − (Current Liabilities − Short-term Debt)
    ΔNWC = NWC(t) − NWC(t−1)
    tc   = effective tax rate, averaged across all years where both tax expense
           and pre-tax income are available and pre-tax income > 0
    CapEx is treated as a positive magnitude (absolute value of yfinance figure)

Returns a dictionary containing all intermediate components per year, the
effective tax rate, FCF/EBIT ratio averages, volatility flag, and warnings.
"""

import math
import statistics
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(year_dict: dict[str, Any] | None, year: str) -> float | None:
    """Safely retrieve a value from a year-keyed dict."""
    if year_dict is None:
        return None
    return year_dict.get(year)


def _sub(a: float | None, b: float | None) -> float | None:
    """Return a - b, or None if either operand is None."""
    if a is None or b is None:
        return None
    return a - b


def _add(a: float | None, b: float | None) -> float | None:
    """Return a + b, or None if either operand is None."""
    if a is None or b is None:
        return None
    return a + b


def _mul(a: float | None, b: float | None) -> float | None:
    """Return a * b, or None if either operand is None."""
    if a is None or b is None:
        return None
    return a * b


def _div(a: float | None, b: float | None) -> float | None:
    """Return a / b, or None if either operand is None or b is zero."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _avg(values: list[float]) -> float | None:
    """Return the mean of a non-empty list, or None."""
    clean = [v for v in values if v is not None and not math.isnan(v)]
    return statistics.mean(clean) if clean else None


def _std(values: list[float]) -> float | None:
    """Return population std dev for a list with ≥2 elements, else None."""
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if len(clean) < 2:
        return None
    return statistics.pstdev(clean)


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def calculate_fcf(financial_data: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate historical FCF from the output of data_fetcher.fetch_financial_data().

    Parameters
    ----------
    financial_data : dict
        Output of data_fetcher.fetch_financial_data().

    Returns
    -------
    dict with keys:
        ticker, effective_tax_rate, tax_rate_years_used,
        annual (per-year components), fcf_ebit_3yr_avg, fcf_ebit_5yr_avg,
        fcf_ebit_std_dev, fcf_ebit_volatility_flag, warnings
    """
    ticker = financial_data.get("ticker", "UNKNOWN")
    calc_warnings: list[str] = []

    inc = financial_data.get("income_statement", {})
    bal = financial_data.get("balance_sheet", {})
    cf  = financial_data.get("cash_flow_statement", {})

    # Collect all years present across any statement, sorted ascending
    all_years: list[str] = sorted(
        {
            yr
            for section in (inc, bal, cf)
            for field_dict in section.values()
            if field_dict
            for yr in field_dict
        }
    )

    if not all_years:
        calc_warnings.append("No year data found in financial_data.")
        return _empty_result(ticker, calc_warnings)

    # ------------------------------------------------------------------
    # Effective tax rate — average across years with valid data
    # ------------------------------------------------------------------
    tax_rate_by_year: dict[str, float] = {}
    for yr in all_years:
        tax  = _get(inc.get("tax_expense"), yr)
        pti  = _get(inc.get("pretax_income"), yr)
        if tax is not None and pti is not None and pti > 0:
            rate = tax / pti
            # Sanity-clamp: ignore implausible rates (negative or >100%)
            if 0.0 <= rate <= 1.0:
                tax_rate_by_year[yr] = rate
            else:
                calc_warnings.append(
                    f"{yr}: Implausible effective tax rate {rate:.1%} "
                    f"(tax={tax:.2e}, pretax={pti:.2e}) — excluded from average."
                )
        else:
            if tax is None:
                calc_warnings.append(f"{yr}: tax_expense is N/A — excluded from tax rate average.")
            if pti is None:
                calc_warnings.append(f"{yr}: pretax_income is N/A — excluded from tax rate average.")

    if not tax_rate_by_year:
        calc_warnings.append(
            "Could not compute effective tax rate — no valid tax/pretax pairs found. "
            "FCF will not be calculated."
        )
        return _empty_result(ticker, calc_warnings)

    effective_tax_rate = statistics.mean(tax_rate_by_year.values())
    tax_rate_years_used = sorted(tax_rate_by_year.keys())

    # ------------------------------------------------------------------
    # NWC per year:  (Current Assets − Cash) − (Current Liabilities − ST Debt)
    # ------------------------------------------------------------------
    nwc_by_year: dict[str, float | None] = {}
    for yr in all_years:
        ca    = _get(bal.get("current_assets"), yr)
        cash  = _get(bal.get("cash_and_equivalents"), yr)
        cl    = _get(bal.get("current_liabilities"), yr)
        std   = _get(bal.get("short_term_debt"), yr)

        operating_ca = _sub(ca, cash)         # Current Assets ex-cash
        operating_cl = _sub(cl, std)          # Current Liabilities ex-ST debt

        nwc = _sub(operating_ca, operating_cl)
        nwc_by_year[yr] = nwc

        if nwc is None:
            missing = [
                name for name, val in
                [("current_assets", ca), ("cash_and_equivalents", cash),
                 ("current_liabilities", cl), ("short_term_debt", std)]
                if val is None
            ]
            calc_warnings.append(
                f"{yr}: NWC could not be computed — missing: {', '.join(missing)}."
            )

    # ------------------------------------------------------------------
    # Per-year FCF and components
    # ------------------------------------------------------------------
    annual: dict[str, dict[str, Any]] = {}

    for i, yr in enumerate(all_years):
        ebit      = _get(inc.get("ebit"), yr)
        da        = _get(inc.get("depreciation_amortization"), yr)
        capex_raw = _get(cf.get("capital_expenditure"), yr)
        opcf      = _get(cf.get("operating_cash_flow"), yr)
        nwc       = nwc_by_year.get(yr)

        # CapEx: yfinance reports as negative cash outflow; we need the
        # positive magnitude for the formula (FCF = ... − CapEx).
        capex = abs(capex_raw) if capex_raw is not None else None

        # ΔNWC = NWC(t) − NWC(t−1); undefined for the first available year
        prior_yr  = all_years[i - 1] if i > 0 else None
        prior_nwc = nwc_by_year.get(prior_yr) if prior_yr else None
        delta_nwc = _sub(nwc, prior_nwc) if prior_yr is not None else None

        # NOPAT = EBIT × (1 − tc)
        nopat = _mul(ebit, (1.0 - effective_tax_rate)) if ebit is not None else None

        # ── FCF ──────────────────────────────────────────────────────────
        # Primary method:  FCF = Operating CF − CapEx
        #   Operating CF (reported via the indirect method) already incorporates
        #   ΔNWC, so this is the most data-rich formula — it only needs the
        #   cash flow statement, which is typically complete across all years.
        # Secondary method: FCF = NOPAT + D&A − ΔNWC − CapEx
        #   Used when Operating CF is unavailable but full balance sheet data is.
        fcf = None
        fcf_method = None

        if opcf is not None and capex is not None:
            fcf = opcf - capex
            fcf_method = "direct"
        elif all(v is not None for v in [nopat, da, delta_nwc, capex]):
            fcf = nopat + da - delta_nwc - capex
            fcf_method = "ebit"
        else:
            missing_direct = [
                n for n, v in [("Operating CF", opcf), ("CapEx", capex)]
                if v is None
            ]
            missing_ebit = [
                n for n, v in [("NOPAT", nopat), ("D&A", da),
                                ("ΔNWC", delta_nwc), ("CapEx", capex)]
                if v is None
            ]
            calc_warnings.append(
                f"{yr}: FCF could not be computed — "
                f"direct method missing {missing_direct}; "
                f"EBIT method missing {missing_ebit}."
            )

        fcf_ebit_ratio = _div(fcf, ebit)

        annual[yr] = {
            "ebit":           ebit,
            "nopat":          nopat,
            "da":             da,
            "nwc":            nwc,
            "delta_nwc":      delta_nwc,
            "capex":          capex,       # positive magnitude
            "opcf":           opcf,
            "fcf":            fcf,
            "fcf_method":     fcf_method,  # "ebit" | "direct" | None
            "fcf_ebit_ratio": fcf_ebit_ratio,
        }

    # ------------------------------------------------------------------
    # FCF/EBIT averages
    # ------------------------------------------------------------------
    valid_ratios: list[tuple[str, float]] = [
        (yr, d["fcf_ebit_ratio"])
        for yr, d in annual.items()
        if d["fcf_ebit_ratio"] is not None
    ]
    # Sort by year ascending (already is, but be explicit)
    valid_ratios.sort(key=lambda x: x[0])
    ratio_values = [v for _, v in valid_ratios]

    # 3-year: three most recent years
    three_yr_ratios = ratio_values[-3:] if len(ratio_values) >= 1 else []
    five_yr_ratios  = ratio_values[-5:] if len(ratio_values) >= 1 else []

    fcf_ebit_3yr_avg = _avg(three_yr_ratios) if len(three_yr_ratios) >= 1 else None
    fcf_ebit_5yr_avg = _avg(five_yr_ratios)  if len(five_yr_ratios)  >= 1 else None

    if len(three_yr_ratios) < 3:
        calc_warnings.append(
            f"3-year FCF/EBIT average uses only {len(three_yr_ratios)} year(s) of data."
        )
    if len(five_yr_ratios) < 5:
        calc_warnings.append(
            f"5-year FCF/EBIT average uses only {len(five_yr_ratios)} year(s) of data."
        )

    # ------------------------------------------------------------------
    # Volatility flag
    # ------------------------------------------------------------------
    std_dev = _std(ratio_values)
    VOLATILITY_THRESHOLD = 0.3
    volatility_flag = (std_dev is not None and std_dev > VOLATILITY_THRESHOLD)

    if volatility_flag:
        calc_warnings.append(
            f"FCF/EBIT ratio is highly volatile — std dev {std_dev:.3f} exceeds "
            f"threshold of {VOLATILITY_THRESHOLD:.1f}. FCF may not be a reliable "
            "proxy for earnings power."
        )

    return {
        "ticker":                  ticker,
        "effective_tax_rate":      effective_tax_rate,
        "tax_rate_years_used":     tax_rate_years_used,
        "annual":                  annual,
        "fcf_ebit_3yr_avg":        fcf_ebit_3yr_avg,
        "fcf_ebit_5yr_avg":        fcf_ebit_5yr_avg,
        "fcf_ebit_std_dev":        std_dev,
        "fcf_ebit_volatility_flag": volatility_flag,
        "warnings":                calc_warnings,
    }


def _empty_result(ticker: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "ticker":                  ticker,
        "effective_tax_rate":      None,
        "tax_rate_years_used":     [],
        "annual":                  {},
        "fcf_ebit_3yr_avg":        None,
        "fcf_ebit_5yr_avg":        None,
        "fcf_ebit_std_dev":        None,
        "fcf_ebit_volatility_flag": False,
        "warnings":                warnings,
    }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _b(value: float | None, pct: bool = False) -> str:
    """Format for table columns: billions, percentage, or ratio."""
    if value is None:
        return "     N/A"
    if pct:
        return f"{value:>8.1%}"
    if abs(value) >= 1e9:
        return f"{value / 1e9:>7.1f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:>7.1f}M"
    return f"{value:>8.4f}"


def _ratio(value: float | None) -> str:
    if value is None:
        return "     N/A"
    return f"{value:>8.2f}x"


def print_fcf_summary(result: dict[str, Any]) -> None:
    """Print a formatted summary table of FCF calculation results."""
    ticker  = result.get("ticker", "?")
    annual  = result.get("annual", {})
    tc      = result.get("effective_tax_rate")
    tc_yrs  = result.get("tax_rate_years_used", [])
    years   = sorted(annual.keys())

    COL = 12
    row_labels = {
        "ebit":          "EBIT",
        "nopat":         f"NOPAT  (tc={tc:.1%})" if tc else "NOPAT",
        "da":            "D&A",
        "opcf":          "Operating CF",
        "nwc":           "NWC",
        "delta_nwc":     "  ΔNWC",
        "capex":         "CapEx",
        "fcf":           "FCF",
        "fcf_ebit_ratio": "FCF / EBIT",
    }

    header_line = f"{'':25}" + "".join(f"{yr:>{COL}}" for yr in years)
    divider = "─" * len(header_line)

    print(f"\n{'='*len(header_line)}")
    print(f"  FCF Analysis — {ticker}")
    tc_note = (
        f"  Effective tax rate: {tc:.2%}  (avg of {', '.join(tc_yrs)})"
        if tc else "  Effective tax rate: N/A"
    )
    print(tc_note)
    print(f"{'='*len(header_line)}")
    print(header_line)
    print(divider)

    for key, label in row_labels.items():
        row = f"{label:<25}"
        for yr in years:
            val = annual.get(yr, {}).get(key)
            if key == "fcf_ebit_ratio":
                row += _ratio(val).rjust(COL)
            else:
                row += _b(val).rjust(COL)
        print(row)

    print(divider)

    # Averages
    avg3 = result.get("fcf_ebit_3yr_avg")
    avg5 = result.get("fcf_ebit_5yr_avg")
    std  = result.get("fcf_ebit_std_dev")
    flag = result.get("fcf_ebit_volatility_flag", False)

    n3 = min(3, len([yr for yr in years if annual.get(yr, {}).get("fcf_ebit_ratio") is not None]))
    n5 = min(5, len([yr for yr in years if annual.get(yr, {}).get("fcf_ebit_ratio") is not None]))

    print(f"\n  FCF/EBIT  3-yr avg ({n3} yr{'s' if n3 != 1 else ''}):  "
          f"{_ratio(avg3).strip()}")
    print(f"  FCF/EBIT  5-yr avg ({n5} yr{'s' if n5 != 1 else ''}):  "
          f"{_ratio(avg5).strip()}")
    print(f"  FCF/EBIT  std dev:          "
          f"{f'{std:.3f}' if std is not None else 'N/A'}"
          f"  {'[HIGH VOLATILITY]' if flag else '[within normal range]'}")

    warnings = result.get("warnings", [])
    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    [!] {w}")

    print(f"{'='*len(header_line)}\n")


# ---------------------------------------------------------------------------
# Entry point — test with AAPL
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from data_fetcher import fetch_financial_data

    print("Fetching AAPL data...")
    financial_data = fetch_financial_data("AAPL")

    if financial_data.get("warnings"):
        print(f"Data fetcher warnings: {financial_data['warnings']}")

    print("Calculating FCF...")
    result = calculate_fcf(financial_data)
    print_fcf_summary(result)

    import pprint
    print("Raw FCF result dictionary:")
    pprint.pprint(result, width=110, sort_dicts=False)
