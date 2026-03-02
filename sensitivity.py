"""
sensitivity.py
--------------
Runs DCF sensitivity analysis across two grids of assumptions and prints
both implied share price and upside/downside tables.

Table 1 — WACC × Terminal Growth Rate
    Rows : WACC  from base_wacc − 2.0%  to base_wacc + 2.0%  in 0.5% steps  (9 values)
    Cols : TGR   from 0.5%              to 4.0%               in 0.5% steps  (8 values)

Table 2 — Revenue Growth Rate × EBIT Margin
    Rows : Revenue growth  from base_g − 4.0%  to base_g + 4.0%  in 1.0% steps  (9 values)
    Cols : EBIT margin     from base_m − 5.0%  to base_m + 5.0%  in 2.5% steps  (5 values)

Both tables are printed twice: once showing implied share price, once showing
% upside / downside versus current market price. The base case cell is
marked with square brackets, e.g. [$140] / [-47.3%].

Usage
-----
    from data_fetcher   import fetch_financial_data
    from fcf_calculator import calculate_fcf
    from assumptions    import build_assumptions
    from dcf_engine     import run_dcf
    from sensitivity    import build_sensitivity, print_sensitivity_tables

    fin    = fetch_financial_data("AAPL")
    fcf    = calculate_fcf(fin)
    assum  = build_assumptions("AAPL", fin)
    base   = run_dcf("AAPL", assum, fcf, fin, growth_rate, tgr)
    sens   = build_sensitivity("AAPL", base, assum, fcf, fin)
    print_sensitivity_tables(sens)
"""

from typing import Any, Callable
from dcf_engine import run_dcf


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

def _grid(start: float, step: float, n: int) -> list[float]:
    """n values starting at start, spaced by step, rounded to 8 dp."""
    return [round(start + i * step, 8) for i in range(n)]


def _closest_idx(values: list[float], target: float) -> int:
    """Index of the element in values numerically closest to target."""
    return min(range(len(values)), key=lambda i: abs(values[i] - target))


# ---------------------------------------------------------------------------
# Sensitivity runner
# ---------------------------------------------------------------------------

def _run_grid(
    ticker_symbol: str,
    assumptions: dict[str, Any],
    fcf_result: dict[str, Any],
    financial_data: dict[str, Any],
    row_values: list[float],
    col_values: list[float],
    make_kwargs: Callable[[float, float], dict],
) -> tuple[list[list], list[list]]:
    """
    Run run_dcf for every (row_val, col_val) combination.

    Returns (prices_2d, upsides_2d) — nested lists indexed [row_idx][col_idx].
    Warnings from individual runs are suppressed to avoid noise across ~100 calls.
    """
    prices:  list[list] = []
    upsides: list[list] = []

    for r_val in row_values:
        p_row: list = []
        u_row: list = []
        for c_val in col_values:
            result = run_dcf(
                ticker_symbol=ticker_symbol,
                assumptions=assumptions,
                fcf_result=fcf_result,
                financial_data=financial_data,
                **make_kwargs(r_val, c_val),
            )
            p_row.append(result.get("implied_share_price"))
            u_row.append(result.get("upside_downside"))
        prices.append(p_row)
        upsides.append(u_row)

    return prices, upsides


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_sensitivity(
    ticker_symbol: str,
    base_dcf: dict[str, Any],
    assumptions: dict[str, Any],
    fcf_result: dict[str, Any],
    financial_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Run sensitivity analysis across two assumption grids.

    Parameters
    ----------
    ticker_symbol : str   — e.g. "AAPL"
    base_dcf      : dict  — output of dcf_engine.run_dcf() (the base case)
    assumptions   : dict  — output of assumptions.build_assumptions()
    fcf_result    : dict  — output of fcf_calculator.calculate_fcf()
    financial_data: dict  — output of data_fetcher.fetch_financial_data()

    Returns
    -------
    dict with keys:
        ticker, current_price, base_inputs, table1, table2, warnings
    Each table dict contains:
        row_values, col_values, base_row_idx, base_col_idx,
        prices (2D list), upsides (2D list), plus descriptive metadata.
    """
    ticker_symbol = ticker_symbol.upper().strip()
    warnings: list[str] = []

    inp         = base_dcf.get("inputs", {})
    base_wacc   = inp.get("wacc")
    base_tgr    = inp.get("terminal_growth_rate")
    base_growth = inp.get("revenue_growth_rate")
    base_margin = inp.get("ebit_margin")
    curr_price  = base_dcf.get("current_price")

    missing = [k for k, v in {
        "wacc": base_wacc, "terminal_growth_rate": base_tgr,
        "revenue_growth_rate": base_growth, "ebit_margin": base_margin,
    }.items() if v is None]
    if missing:
        warnings.append(f"Base case missing required inputs: {missing} — cannot build grids.")
        return {"ticker": ticker_symbol, "table1": None, "table2": None,
                "current_price": curr_price, "warnings": warnings}

    # ── Table 1: WACC × Terminal Growth Rate ─────────────────────────
    # WACC: base ± 2%  in 0.5% steps → 9 rows
    # TGR : 0.5% → 4.0% in 0.5% steps → 8 cols
    wacc_values = _grid(base_wacc - 0.02, 0.005, 9)
    tgr_values  = _grid(0.005, 0.005, 8)

    base_wacc_idx = _closest_idx(wacc_values, base_wacc)
    base_tgr_idx  = _closest_idx(tgr_values,  base_tgr)

    t1_prices, t1_upsides = _run_grid(
        ticker_symbol, assumptions, fcf_result, financial_data,
        row_values=wacc_values,
        col_values=tgr_values,
        make_kwargs=lambda w, t: dict(
            revenue_growth_rate=base_growth,
            terminal_growth_rate=t,
            wacc_override=w,
        ),
    )

    table1 = {
        "title":       "TABLE 1  —  WACC × Terminal Growth Rate",
        "row_label":   "WACC",
        "col_label":   "Terminal Growth Rate",
        "row_values":  wacc_values,
        "col_values":  tgr_values,
        "base_row_idx": base_wacc_idx,
        "base_col_idx": base_tgr_idx,
        "prices":      t1_prices,
        "upsides":     t1_upsides,
    }

    # ── Table 2: Revenue Growth × EBIT Margin ────────────────────────
    # Growth: base ± 4%  in 1.0% steps → 9 rows
    # Margin: base ± 5%  in 2.5% steps → 5 cols
    growth_values = _grid(base_growth - 0.04, 0.01, 9)
    margin_values = _grid(base_margin - 0.05, 0.025, 5)

    base_growth_idx = _closest_idx(growth_values, base_growth)
    base_margin_idx = _closest_idx(margin_values, base_margin)

    t2_prices, t2_upsides = _run_grid(
        ticker_symbol, assumptions, fcf_result, financial_data,
        row_values=growth_values,
        col_values=margin_values,
        make_kwargs=lambda g, m: dict(
            revenue_growth_rate=g,
            terminal_growth_rate=base_tgr,
            ebit_margin_override=m,
        ),
    )

    table2 = {
        "title":        "TABLE 2  —  Revenue Growth Rate × EBIT Margin",
        "row_label":    "Rev. Growth",
        "col_label":    "EBIT Margin",
        "row_values":   growth_values,
        "col_values":   margin_values,
        "base_row_idx": base_growth_idx,
        "base_col_idx": base_margin_idx,
        "prices":       t2_prices,
        "upsides":      t2_upsides,
    }

    return {
        "ticker":       ticker_symbol,
        "current_price": curr_price,
        "base_inputs": {
            "wacc":           base_wacc,
            "tgr":            base_tgr,
            "revenue_growth": base_growth,
            "ebit_margin":    base_margin,
        },
        "table1":   table1,
        "table2":   table2,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def _fmt_price(v: float | None) -> str:
    """Compact share price string (1 decimal, dollar sign)."""
    if v is None:
        return "N/A"
    return f"${v:.1f}"


def _fmt_upside(v: float | None) -> str:
    """Signed percentage string."""
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1%}"


def _highlight(s: str, is_base: bool) -> str:
    """Wrap string in brackets when it is the base case cell."""
    return f"[{s}]" if is_base else s


def _print_grid_table(
    table: dict[str, Any],
    subtitle: str,
    cell_fn: Callable[[float | None], str],
    row_fmt: Callable[[float], str],
    col_fmt: Callable[[float], str],
    data_key: str,          # "prices" or "upsides"
) -> None:
    """
    Print one sensitivity sub-table (price or upside) with base case highlighted.

    Layout
    ------
    Corner label + header row of col values
    ─── separator ───
    One data row per row_value
    """
    row_values  = table["row_values"]
    col_values  = table["col_values"]
    data        = table[data_key]
    b_row       = table["base_row_idx"]
    b_col       = table["base_col_idx"]
    row_label   = table["row_label"]

    # Compute column widths dynamically so every value fits
    # Min cell width is max of (header string len, longest formatted value) + 2 padding
    col_widths: list[int] = []
    for ci, cv in enumerate(col_values):
        hdr_s  = _highlight(col_fmt(cv), ci == b_col)
        vals   = [_highlight(cell_fn(data[ri][ci]), ri == b_row and ci == b_col)
                  for ri in range(len(row_values))]
        col_widths.append(max(len(s) for s in [hdr_s] + vals) + 2)

    # Row label column width
    row_hdrs = [_highlight(row_fmt(rv), ri == b_row) for ri, rv in enumerate(row_values)]
    label_w  = max(len(s) for s in row_hdrs + [row_label]) + 2

    total_w = label_w + sum(col_widths)
    dsep    = "═" * total_w
    sep     = "─" * total_w

    print(dsep)
    if subtitle:
        print(f"  {subtitle}")
    print(dsep)

    # Header row
    corner = row_label.rjust(label_w)
    hdr    = corner + "".join(
        _highlight(col_fmt(cv), ci == b_col).rjust(cw)
        for ci, (cv, cw) in enumerate(zip(col_values, col_widths))
    )
    print(hdr)
    print(sep)

    # Data rows
    for ri, (_, row_hdr) in enumerate(zip(row_values, row_hdrs)):
        row = row_hdr.rjust(label_w)
        for ci, (cv, cw) in enumerate(zip(col_values, col_widths)):
            raw      = data[ri][ci]
            cell_str = _highlight(cell_fn(raw), ri == b_row and ci == b_col)
            row     += cell_str.rjust(cw)
        print(row)

    print(dsep)
    print()


def print_sensitivity_tables(result: dict[str, Any]) -> None:
    """
    Print both sensitivity tables (price and upside) for a build_sensitivity() result.
    Each sensitivity analysis produces two sub-tables: implied price and % upside.
    Base case cells are enclosed in [brackets].
    """
    ticker     = result.get("ticker", "?")
    curr_price = result.get("current_price")
    cp_str     = f"${curr_price:.2f}" if curr_price else "N/A"

    def price_subtitle(t: dict) -> str:
        return (
            f"{t['title']}  —  Implied Share Price\n"
            f"  Base: {t['row_label']} {_fmt_base_row(t)}  ×  "
            f"{t['col_label']} {_fmt_base_col(t)}"
            f"   |   Current price: {cp_str}   |   [base case in brackets]"
        )

    def upside_subtitle(t: dict) -> str:
        return (
            f"{t['title']}  —  Upside / Downside vs {cp_str}\n"
            f"  Base: {t['row_label']} {_fmt_base_row(t)}  ×  "
            f"{t['col_label']} {_fmt_base_col(t)}"
        )

    for key, row_fmt, col_fmt in [
        ("table1", lambda v: f"{v:.2%}", lambda v: f"{v:.1%}"),
        ("table2", lambda v: f"{v:.2%}", lambda v: f"{v:.1%}"),
    ]:
        t = result.get(key)
        if t is None:
            print(f"[{key} unavailable]\n")
            continue

        print(f"\n  {ticker}  ·  {t['title']}\n")

        _print_grid_table(
            table=t,
            subtitle=price_subtitle(t),
            cell_fn=_fmt_price,
            row_fmt=row_fmt, col_fmt=col_fmt,
            data_key="prices",
        )

        _print_grid_table(
            table=t,
            subtitle=upside_subtitle(t),
            cell_fn=_fmt_upside,
            row_fmt=row_fmt, col_fmt=col_fmt,
            data_key="upsides",
        )


def _fmt_base_row(table: dict) -> str:
    """Format the base case row header value for the subtitle."""
    return f"{table['row_values'][table['base_row_idx']]:.2%}"


def _fmt_base_col(table: dict) -> str:
    """Format the base case col header value for the subtitle."""
    return f"{table['col_values'][table['base_col_idx']]:.2%}"


# ---------------------------------------------------------------------------
# Entry point — test on AAPL
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from data_fetcher   import fetch_financial_data
    from fcf_calculator import calculate_fcf
    from assumptions    import build_assumptions

    TICKER          = "AAPL"
    TERMINAL_GROWTH = 0.025

    print(f"[1/4] Fetching {TICKER} financial data...")
    fin = fetch_financial_data(TICKER)

    print(f"[2/4] Calculating FCF...")
    fcf_res = calculate_fcf(fin)

    print(f"[3/4] Building assumptions...")
    assum = build_assumptions(TICKER, fin)

    # Select growth rate (same logic as dcf_engine __main__)
    arg = assum.get("analyst_revenue_growth", {})
    growth_rate, growth_source = next(
        ((v, s) for v, s in [
            (arg.get("next_year",    {}).get("value"), "analyst next-year"),
            (arg.get("current_year", {}).get("value"), "analyst current-year"),
            (assum.get("revenue_cagr_3yr", {}).get("value"), "3yr CAGR"),
        ] if v is not None),
        (None, "none"),
    )
    if growth_rate is None:
        print("ERROR: No revenue growth rate available.")
        raise SystemExit(1)

    print(f"[4/4] Running base DCF  (growth {growth_rate:.2%}  |  TGR {TERMINAL_GROWTH:.2%})...")
    base_dcf = run_dcf(
        ticker_symbol=TICKER,
        assumptions=assum,
        fcf_result=fcf_res,
        financial_data=fin,
        revenue_growth_rate=growth_rate,
        terminal_growth_rate=TERMINAL_GROWTH,
    )

    base_price = base_dcf.get("implied_share_price")
    curr_price = base_dcf.get("current_price")
    base_wacc  = base_dcf["inputs"].get("wacc")
    print(f"\n  Base case: WACC {base_wacc:.2%}  |  implied ${base_price:.2f}"
          f"  |  current ${curr_price:.2f}\n")

    print("Running sensitivity grids (Table 1: 9×8, Table 2: 9×5)...")
    sens = build_sensitivity(TICKER, base_dcf, assum, fcf_res, fin)

    if sens.get("warnings"):
        for w in sens["warnings"]:
            print(f"  [!] {w}")

    print_sensitivity_tables(sens)
