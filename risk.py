"""
risk.py
-------
Produces a structured risk assessment from financial statement data and FCF results.
Pure calculation — no network calls, no yfinance imports.

Metrics
-------
  1. leverage_ratio       — Total Debt / EBIT (most recent year with both)
  2. interest_coverage    — EBIT / |Interest Expense| (most recent year with both)
  3. fcf_volatility       — Std dev of FCF/EBIT ratios (pre-computed in fcf_result)
  4. revenue_consistency  — Std dev of year-over-year revenue growth rates
  5. debt_trend           — CAGR of total debt over available years
  6. fcf_trend            — Linear slope of FCF normalised by mean FCF

Traffic light ratings
---------------------
  GREEN  — within safe range
  AMBER  — warrants monitoring
  RED    — elevated risk
  N/A    — insufficient data to compute

Thresholds
----------
  leverage_ratio      :  Green < 2×    Amber 2–4×     Red > 4× (or EBIT ≤ 0)
  interest_coverage   :  Green > 8×    Amber 3–8×     Red < 3× (or EBIT ≤ 0)
  fcf_volatility      :  Green < 0.10  Amber 0.10–0.25  Red > 0.25
  revenue_consistency :  Green < 5%    Amber 5–15%    Red > 15%
  debt_trend (CAGR)   :  Green < 0%    Amber 0–8%     Red > 8%
  fcf_trend (norm.)   :  Green > +5%   Amber ±5%      Red < −5%

Overall score
-------------
  Starts at 10.  GREEN = no deduction.  AMBER = −1.  RED = −2.  N/A = no deduction.
  Floored at 0.
"""

import math
import statistics
from typing import Any


# ---------------------------------------------------------------------------
# Thresholds (all positive-normalised — comparison direction set in each fn)
# ---------------------------------------------------------------------------

_LEV_AMBER = 2.0      # Debt/EBIT — lower is safer
_LEV_RED   = 4.0

_COV_AMBER = 8.0      # EBIT/Interest — higher is safer
_COV_RED   = 3.0

_VOL_AMBER = 0.10     # FCF/EBIT std dev — lower is safer
_VOL_RED   = 0.25

_CONS_AMBER = 0.05    # Revenue growth std dev — lower is safer
_CONS_RED   = 0.15

_DEBT_AMBER = 0.00    # Debt CAGR — negative (shrinking) is green
_DEBT_RED   = 0.08    # > 8 % per year

_FCF_GREEN  = 0.05    # Normalised FCF slope — positive is better
_FCF_RED    = -0.05

_DEDUCTIONS = {"green": 0.0, "amber": 1.0, "red": 2.0, "na": 0.0}

_SCORE_LABELS = [
    (9, "Very Low Risk"),
    (7, "Low Risk"),
    (5, "Moderate Risk"),
    (3, "High Risk"),
    (0, "Very High Risk"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(value: Any) -> float | None:
    try:
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _most_recent(year_dict: dict | None) -> tuple[str | None, float | None]:
    """Return (year_str, value) for the most recent non-None entry."""
    if not year_dict:
        return None, None
    for yr in sorted(year_dict.keys(), reverse=True):
        v = _safe(year_dict.get(yr))
        if v is not None:
            return yr, v
    return None, None


def _valid_series(year_dict: dict | None) -> list[tuple[str, float]]:
    """Return sorted (year, value) pairs where value is a valid float."""
    if not year_dict:
        return []
    return [
        (yr, _safe(v))
        for yr, v in sorted(year_dict.items())
        if _safe(v) is not None
    ]


def _linear_slope_normalised(values: list[float]) -> float | None:
    """
    Slope of OLS linear regression through the values, normalised by their
    mean absolute value.  Returns fraction-per-period (e.g. 0.09 = 9 % / yr).
    """
    n = len(values)
    if n < 2:
        return None
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    cov    = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    var_x  = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return 0.0
    slope    = cov / var_x
    mean_abs = abs(mean_y) if mean_y != 0 else 1.0
    return slope / mean_abs


def _metric(
    key: str,
    label: str,
    value: float | None,
    value_str: str,
    rating: str,
    note: str,
    threshold: str,
) -> dict[str, Any]:
    return {
        "key":       key,
        "label":     label,
        "value":     value,
        "value_str": value_str,
        "rating":    rating,
        "note":      note,
        "threshold": threshold,
    }


# ---------------------------------------------------------------------------
# Individual metric calculators
# ---------------------------------------------------------------------------

def _calc_leverage(inc: dict, bal: dict, warnings: list) -> dict:
    """Total Debt / EBIT — most recent year where both are non-None."""
    ebit_series  = _valid_series(inc.get("ebit"))
    debt_series  = _valid_series(bal.get("total_debt"))

    ebit_by_yr  = {yr: v for yr, v in ebit_series}
    debt_by_yr  = {yr: v for yr, v in debt_series}

    # Find most recent year with both
    common = sorted(set(ebit_by_yr) & set(debt_by_yr), reverse=True)
    for yr in common:
        ebit = ebit_by_yr[yr]
        debt = debt_by_yr[yr]
        if ebit <= 0:
            return _metric(
                "leverage_ratio", "Leverage  (Debt / EBIT)",
                None, "N/A", "red",
                f"FY{yr}: EBIT ≤ 0 — leverage undefined; negative operating income is a concern.",
                f"Green < {_LEV_AMBER}×  |  Amber {_LEV_AMBER}–{_LEV_RED}×  |  Red > {_LEV_RED}×",
            )
        ratio = debt / ebit
        if ratio < _LEV_AMBER:
            rating = "green"
        elif ratio < _LEV_RED:
            rating = "amber"
        else:
            rating = "red"
        return _metric(
            "leverage_ratio", "Leverage  (Debt / EBIT)",
            ratio, f"{ratio:.2f}×", rating,
            f"FY{yr}: ${debt/1e9:.1f}B debt  /  ${ebit/1e9:.1f}B EBIT",
            f"Green < {_LEV_AMBER}×  |  Amber {_LEV_AMBER}–{_LEV_RED}×  |  Red > {_LEV_RED}×",
        )

    warnings.append("Leverage: no year with both EBIT and total debt available.")
    return _metric(
        "leverage_ratio", "Leverage  (Debt / EBIT)",
        None, "N/A", "na", "Insufficient data.", ""
    )


def _calc_interest_coverage(inc: dict, warnings: list) -> dict:
    """EBIT / |Interest Expense| — most recent year where both are non-None."""
    ebit_series = _valid_series(inc.get("ebit"))
    int_series  = _valid_series(inc.get("interest_expense"))

    ebit_by_yr = {yr: v for yr, v in ebit_series}
    int_by_yr  = {yr: v for yr, v in int_series}

    common = sorted(set(ebit_by_yr) & set(int_by_yr), reverse=True)
    for yr in common:
        ebit = ebit_by_yr[yr]
        ie   = abs(int_by_yr[yr])
        if ie == 0:
            continue
        if ebit <= 0:
            return _metric(
                "interest_coverage", "Interest Coverage  (EBIT / Interest)",
                None, "N/A", "red",
                f"FY{yr}: EBIT ≤ 0 — cannot cover interest; distress signal.",
                f"Green > {_COV_AMBER}×  |  Amber {_COV_RED}–{_COV_AMBER}×  |  Red < {_COV_RED}×",
            )
        ratio = ebit / ie
        if ratio > _COV_AMBER:
            rating = "green"
        elif ratio > _COV_RED:
            rating = "amber"
        else:
            rating = "red"
        # Note when data is stale
        ebit_yrs = sorted(ebit_by_yr.keys(), reverse=True)
        latest_ebit_yr = ebit_yrs[0] if ebit_yrs else yr
        stale = f"  [latest EBIT: FY{latest_ebit_yr}; interest expense last reported: FY{yr}]" \
                if latest_ebit_yr != yr else ""
        return _metric(
            "interest_coverage", "Interest Coverage  (EBIT / Interest)",
            ratio, f"{ratio:.1f}×", rating,
            f"FY{yr}: ${ebit/1e9:.1f}B EBIT  /  ${ie/1e9:.2f}B interest expense{stale}",
            f"Green > {_COV_AMBER}×  |  Amber {_COV_RED}–{_COV_AMBER}×  |  Red < {_COV_RED}×",
        )

    warnings.append("Interest coverage: no year with both EBIT and interest expense available.")
    return _metric(
        "interest_coverage", "Interest Coverage  (EBIT / Interest)",
        None, "N/A", "na",
        "Interest expense not reported — possibly zero-interest or unreported debt.",
        f"Green > {_COV_AMBER}×  |  Amber {_COV_RED}–{_COV_AMBER}×  |  Red < {_COV_RED}×",
    )


def _calc_fcf_volatility(fcf_result: dict, warnings: list) -> dict:
    """Std dev of FCF/EBIT ratios — already computed in fcf_result."""
    std_dev = _safe(fcf_result.get("fcf_ebit_std_dev"))
    yrs_used = [
        yr for yr, d in fcf_result.get("annual", {}).items()
        if d.get("fcf_ebit_ratio") is not None
    ]
    n = len(yrs_used)

    if std_dev is None:
        warnings.append("FCF volatility: std dev not available in fcf_result.")
        return _metric(
            "fcf_volatility", "FCF Volatility  (σ of FCF/EBIT)",
            None, "N/A", "na", "Insufficient FCF data.", ""
        )

    if std_dev < _VOL_AMBER:
        rating = "green"
    elif std_dev < _VOL_RED:
        rating = "amber"
    else:
        rating = "red"

    yr_str = f"FY{min(yrs_used)}–FY{max(yrs_used)}" if n >= 2 else (f"FY{yrs_used[0]}" if n == 1 else "")
    return _metric(
        "fcf_volatility", "FCF Volatility  (σ of FCF/EBIT)",
        std_dev, f"{std_dev:.3f}", rating,
        f"Std dev of FCF/EBIT ratios over {n} year{'s' if n != 1 else ''}"
        + (f"  ({yr_str})" if yr_str else ""),
        f"Green < {_VOL_AMBER}  |  Amber {_VOL_AMBER}–{_VOL_RED}  |  Red > {_VOL_RED}",
    )


def _calc_revenue_consistency(inc: dict, warnings: list) -> dict:
    """Std dev of year-over-year revenue growth rates."""
    series = _valid_series(inc.get("revenue"))      # [(year, revenue), ...]

    if len(series) < 3:
        warnings.append("Revenue consistency: need ≥ 3 revenue years for 2 growth observations.")
        return _metric(
            "revenue_consistency", "Revenue Consistency  (σ of YoY growth)",
            None, "N/A", "na", "Fewer than 3 years of revenue data.", ""
        )

    growth_rates = []
    for i in range(1, len(series)):
        yr_prev, rev_prev = series[i - 1]
        yr_curr, rev_curr = series[i]
        if rev_prev and rev_prev != 0:
            growth_rates.append((rev_curr - rev_prev) / abs(rev_prev))

    if len(growth_rates) < 2:
        warnings.append("Revenue consistency: fewer than 2 valid growth rates.")
        return _metric(
            "revenue_consistency", "Revenue Consistency  (σ of YoY growth)",
            None, "N/A", "na", "Insufficient revenue data for std dev.", ""
        )

    std_dev = statistics.pstdev(growth_rates)
    first_yr = series[0][0]
    last_yr  = series[-1][0]

    if std_dev < _CONS_AMBER:
        rating = "green"
    elif std_dev < _CONS_RED:
        rating = "amber"
    else:
        rating = "red"

    return _metric(
        "revenue_consistency", "Revenue Consistency  (σ of YoY growth)",
        std_dev, f"{std_dev:.1%}", rating,
        f"Std dev of {len(growth_rates)} YoY growth rates  (FY{first_yr}–FY{last_yr})",
        f"Green < {_CONS_AMBER:.0%}  |  Amber {_CONS_AMBER:.0%}–{_CONS_RED:.0%}  |  Red > {_CONS_RED:.0%}",
    )


def _calc_debt_trend(bal: dict, warnings: list) -> dict:
    """CAGR of total debt from first to last available year."""
    series = _valid_series(bal.get("total_debt"))   # already sorted ascending

    if len(series) < 2:
        warnings.append("Debt trend: need ≥ 2 years of total debt data.")
        return _metric(
            "debt_trend", "Debt Trend  (Total Debt CAGR)",
            None, "N/A", "na", "Fewer than 2 years of total debt data.", ""
        )

    yr_first, debt_first = series[0]
    yr_last,  debt_last  = series[-1]
    n_years = int(yr_last) - int(yr_first)

    if n_years <= 0 or debt_first <= 0:
        warnings.append("Debt trend: cannot compute CAGR (invalid year span or zero debt).")
        return _metric(
            "debt_trend", "Debt Trend  (Total Debt CAGR)",
            None, "N/A", "na", "Cannot compute CAGR.", ""
        )

    cagr = (debt_last / debt_first) ** (1.0 / n_years) - 1.0

    if cagr < _DEBT_AMBER:
        rating = "green"
        direction = "decreasing"
    elif cagr < _DEBT_RED:
        rating = "amber"
        direction = "slightly increasing"
    else:
        rating = "red"
        direction = "strongly increasing"

    return _metric(
        "debt_trend", "Debt Trend  (Total Debt CAGR)",
        cagr, f"{cagr:+.1%}/yr", rating,
        f"FY{yr_first} ${debt_first/1e9:.1f}B → FY{yr_last} ${debt_last/1e9:.1f}B"
        f"  ({direction}, {n_years}-yr CAGR)",
        f"Green < {_DEBT_AMBER:.0%}  |  Amber {_DEBT_AMBER:.0%}–{_DEBT_RED:.0%}  |  Red > {_DEBT_RED:.0%}",
    )


def _calc_fcf_trend(fcf_result: dict, warnings: list) -> dict:
    """Normalised linear slope of FCF over available years."""
    annual = fcf_result.get("annual", {})
    fcf_pairs = sorted(
        [(yr, _safe(d.get("fcf"))) for yr, d in annual.items() if _safe(d.get("fcf")) is not None]
    )   # [(year_str, fcf_value), ...]

    if len(fcf_pairs) < 2:
        warnings.append("FCF trend: need ≥ 2 years of FCF data.")
        return _metric(
            "fcf_trend", "FCF Trend  (normalised slope)",
            None, "N/A", "na", "Fewer than 2 years of FCF data.", ""
        )

    values   = [v for _, v in fcf_pairs]
    slope_n  = _linear_slope_normalised(values)

    if slope_n is None:
        return _metric(
            "fcf_trend", "FCF Trend  (normalised slope)",
            None, "N/A", "na", "Could not compute slope.", ""
        )

    if slope_n > _FCF_GREEN:
        rating, direction = "green", "improving"
    elif slope_n >= _FCF_RED:
        rating, direction = "amber", "stable"
    else:
        rating, direction = "red", "deteriorating"

    yr_first = fcf_pairs[0][0]
    yr_last  = fcf_pairs[-1][0]
    fcf_first = fcf_pairs[0][1]
    fcf_last  = fcf_pairs[-1][1]

    return _metric(
        "fcf_trend", "FCF Trend  (normalised slope)",
        slope_n, f"{slope_n:+.1%}/yr", rating,
        f"FY{yr_first} ${fcf_first/1e9:.1f}B → FY{yr_last} ${fcf_last/1e9:.1f}B  "
        f"({direction}; linear slope {slope_n:+.1%}/yr of mean FCF)",
        f"Green > {_FCF_GREEN:+.0%}/yr  |  Amber ±{_FCF_GREEN:.0%}  |  Red < {_FCF_RED:+.0%}/yr",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_risk(
    financial_data: dict[str, Any],
    fcf_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute a structured risk assessment from pre-fetched financial data.

    Parameters
    ----------
    financial_data : dict — output of data_fetcher.fetch_financial_data()
    fcf_result     : dict — output of fcf_calculator.calculate_fcf()

    Returns
    -------
    dict with keys:
        ticker, metrics (dict of 6 metric dicts), overall_score,
        overall_label, score_breakdown, warnings
    """
    ticker   = financial_data.get("ticker", "UNKNOWN")
    inc      = financial_data.get("income_statement", {})
    bal      = financial_data.get("balance_sheet",    {})
    warnings: list[str] = []

    metrics: dict[str, dict] = {
        "leverage_ratio":      _calc_leverage(inc, bal, warnings),
        "interest_coverage":   _calc_interest_coverage(inc, warnings),
        "fcf_volatility":      _calc_fcf_volatility(fcf_result, warnings),
        "revenue_consistency": _calc_revenue_consistency(inc, warnings),
        "debt_trend":          _calc_debt_trend(bal, warnings),
        "fcf_trend":           _calc_fcf_trend(fcf_result, warnings),
    }

    # Overall score
    deductions = {
        key: _DEDUCTIONS[m["rating"]]
        for key, m in metrics.items()
    }
    total_deducted = sum(deductions.values())
    score = max(0.0, 10.0 - total_deducted)

    label = next(
        lbl for threshold, lbl in _SCORE_LABELS if score >= threshold
    )

    return {
        "ticker":          ticker,
        "metrics":         metrics,
        "overall_score":   score,
        "overall_label":   label,
        "score_breakdown": deductions,
        "warnings":        warnings,
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

_BADGE = {
    "green": "[GREEN]",
    "amber": "[AMBER]",
    "red":   "[RED  ]",
    "na":    "[N/A  ]",
}

_SCORE_BAR_WIDTH = 20   # characters for the visual score bar


def _score_bar(score: float) -> str:
    """Return a simple ASCII bar representing score / 10."""
    filled = round(score)
    return "█" * filled + "░" * (10 - filled)


def print_risk_dashboard(result: dict[str, Any]) -> None:
    """Print a formatted risk dashboard from assess_risk() output."""
    ticker  = result.get("ticker", "?")
    metrics = result.get("metrics", {})
    score   = result.get("overall_score", 0.0)
    label   = result.get("overall_label", "")
    brkdwn  = result.get("score_breakdown", {})
    warns   = result.get("warnings", [])

    W    = 76
    dsep = "═" * W
    sep  = "─" * W

    LBL_W  = 38    # metric label column
    VAL_W  = 9     # value column
    RTNG_W = 9     # rating badge column

    print(f"\n{dsep}")
    print(f"  Risk Dashboard  —  {ticker}")
    print(dsep)

    # ── Metric rows ──────────────────────────────────────────────────
    print(f"\n  {'METRIC':<{LBL_W}} {'VALUE':>{VAL_W}}  {'RATING':<{RTNG_W}}  NOTE")
    print(f"  {sep}")

    for key, m in metrics.items():
        badge  = _BADGE.get(m["rating"], f"[{m['rating'].upper():<5}]")
        label_str = m["label"]
        val_str   = m["value_str"]
        note      = m["note"]

        # Truncate note if it would overflow (wrap isn't available in plain print)
        max_note = W - LBL_W - VAL_W - RTNG_W - 8
        if len(note) > max_note:
            note = note[:max_note - 3] + "..."

        print(f"  {label_str:<{LBL_W}} {val_str:>{VAL_W}}  {badge:<{RTNG_W}}  {note}")

    # ── Score ─────────────────────────────────────────────────────────
    print(f"\n  {sep}")

    deducted_metrics = {k: v for k, v in brkdwn.items() if v > 0}
    if deducted_metrics:
        print(f"  Deductions:")
        for key, ded in deducted_metrics.items():
            rating = metrics[key]["rating"].upper()
            print(f"    {metrics[key]['label']:<{LBL_W - 4}} {rating:<8}  −{ded:.1f}")
    else:
        print(f"  No deductions — all metrics GREEN.")

    print(f"\n  {sep}")
    bar = _score_bar(score)
    print(f"  OVERALL RISK SCORE   {score:.1f} / 10   {bar}   {label}")
    print(f"  {sep}")

    # ── Thresholds legend ─────────────────────────────────────────────
    print(f"\n  Thresholds:")
    for m in metrics.values():
        if m["threshold"]:
            print(f"    {m['label']:<{LBL_W - 4}}  {m['threshold']}")

    # ── Warnings ──────────────────────────────────────────────────────
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

    print("Fetching AAPL data...")
    fin = fetch_financial_data("AAPL")

    print("Calculating FCF...")
    fcf = calculate_fcf(fin)

    print("Assessing risk...")
    result = assess_risk(fin, fcf)

    print_risk_dashboard(result)

    print("Raw result:")
    pprint.pprint(result, width=100, sort_dicts=False)
