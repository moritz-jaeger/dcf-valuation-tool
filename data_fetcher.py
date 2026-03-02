"""
data_fetcher.py
---------------
Fetches and cleans financial statement data for a US stock ticker using yfinance.

Returns a dictionary containing:
  - Income statement items (5-year annual)
  - Balance sheet items (5-year annual)
  - Cash flow statement items (5-year annual)
  - Market data (current price, shares, market cap, beta)
  - warnings: list of any line items that could not be retrieved
"""

import warnings as _warnings
from typing import Any
import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Field name aliases
# Each entry is a list of candidate column names tried in order.
# yfinance has changed naming conventions across versions; aliases handle that.
# ---------------------------------------------------------------------------

INCOME_ALIASES: dict[str, list[str]] = {
    "revenue": [
        "Total Revenue",
        "TotalRevenue",
        "Revenue",
    ],
    "ebit": [
        "EBIT",
        "Ebit",
        "Operating Income",
        "OperatingIncome",
    ],
    "depreciation_amortization": [
        "Reconciled Depreciation",
        "ReconciledDepreciation",
        "Depreciation And Amortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "interest_expense": [
        "Interest Expense",
        "InterestExpense",
        "Interest Expense Non Operating",
        "InterestExpenseNonOperating",
        "Net Interest Income",
    ],
    "tax_expense": [
        "Tax Provision",
        "TaxProvision",
        "Income Tax Expense",
        "IncomeTaxExpense",
    ],
    "pretax_income": [
        "Pretax Income",
        "PretaxIncome",
        "Pre Tax Income",
        "EarningsBeforeTax",
    ],
}

BALANCE_ALIASES: dict[str, list[str]] = {
    "current_assets": [
        "Current Assets",
        "CurrentAssets",
        "Total Current Assets",
        "TotalCurrentAssets",
    ],
    "cash_and_equivalents": [
        "Cash And Cash Equivalents",
        "CashAndCashEquivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
    ],
    "current_liabilities": [
        "Current Liabilities",
        "CurrentLiabilities",
        "Total Current Liabilities",
        "TotalCurrentLiabilities",
    ],
    "short_term_debt": [
        "Current Debt",
        "CurrentDebt",
        "Short Term Debt",
        "ShortTermDebt",
        "Current Debt And Capital Lease Obligation",
        "CurrentDebtAndCapitalLeaseObligation",
    ],
    "total_debt": [
        "Total Debt",
        "TotalDebt",
        "Long Term Debt And Capital Lease Obligation",
    ],
}

CASHFLOW_ALIASES: dict[str, list[str]] = {
    "operating_cash_flow": [
        "Operating Cash Flow",
        "OperatingCashFlow",
        "Total Cash From Operating Activities",
        "Cash From Operating Activities",
    ],
    "capital_expenditure": [
        "Capital Expenditure",
        "CapitalExpenditure",
        "Capital Expenditures",
        "Purchase Of Property Plant And Equipment",
        "PurchaseOfPropertyPlantAndEquipment",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_row(df: pd.DataFrame, aliases: list[str], warn_name: str, warnings: list[str]) -> dict[str, Any] | None:
    """
    Try each alias in order; return a year-keyed dict of values for the first
    matching row, or None if none found (adding a warning entry).
    """
    for alias in aliases:
        if alias in df.index:
            series = df.loc[alias]
            # Convert Timestamp index to year strings
            return {str(ts.year): _safe_float(v) for ts, v in series.items()}
    warnings.append(f"Could not find '{warn_name}' — tried: {aliases}")
    return None


def _safe_float(value: Any) -> float | None:
    """Convert a value to float, returning None for NaN/None."""
    try:
        f = float(value)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _limit_to_5_years(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep only the 5 most-recent years (keys are year strings)."""
    if data is None:
        return None
    sorted_years = sorted(data.keys(), reverse=True)[:5]
    return {yr: data[yr] for yr in sorted(sorted_years)}


def _get_statement(ticker: yf.Ticker, statement: str) -> pd.DataFrame | None:
    """
    Retrieve an annual financial statement DataFrame, trying the newer API
    attribute names first, then older aliases.
    """
    attr_map = {
        "income":    ["income_stmt", "financials"],
        "balance":   ["balance_sheet", "quarterly_balance_sheet"],
        "cashflow":  ["cashflow", "cash_flow"],
    }
    for attr in attr_map.get(statement, []):
        try:
            df = getattr(ticker, attr)
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_financial_data(ticker_symbol: str) -> dict[str, Any]:
    """
    Fetch cleaned financial data for a US ticker.

    Parameters
    ----------
    ticker_symbol : str
        US stock ticker (e.g. "AAPL").

    Returns
    -------
    dict with keys:
        ticker, income_statement, balance_sheet, cash_flow_statement,
        market_data, warnings
    """
    ticker_symbol = ticker_symbol.upper().strip()
    fetched_warnings: list[str] = []

    # ------------------------------------------------------------------
    # Download ticker
    # ------------------------------------------------------------------
    try:
        ticker = yf.Ticker(ticker_symbol)
    except Exception as exc:
        return {"ticker": ticker_symbol, "error": str(exc), "warnings": [str(exc)]}

    # ------------------------------------------------------------------
    # Financial statements
    # ------------------------------------------------------------------
    income_df  = _get_statement(ticker, "income")
    balance_df = _get_statement(ticker, "balance")
    cashflow_df = _get_statement(ticker, "cashflow")

    if income_df is None:
        fetched_warnings.append("Income statement unavailable — all income items missing.")
    if balance_df is None:
        fetched_warnings.append("Balance sheet unavailable — all balance sheet items missing.")
    if cashflow_df is None:
        fetched_warnings.append("Cash flow statement unavailable — all cash flow items missing.")

    def _extract(df, aliases_dict):
        result = {}
        for key, aliases in aliases_dict.items():
            if df is not None:
                raw = _extract_row(df, aliases, key, fetched_warnings)
            else:
                raw = None
                fetched_warnings.append(f"Could not find '{key}' — statement unavailable.")
            result[key] = _limit_to_5_years(raw)
        return result

    income_data   = _extract(income_df,   INCOME_ALIASES)
    balance_data  = _extract(balance_df,  BALANCE_ALIASES)
    cashflow_data = _extract(cashflow_df, CASHFLOW_ALIASES)

    # ------------------------------------------------------------------
    # Market data from ticker.info
    # ------------------------------------------------------------------
    market_data: dict[str, Any] = {}
    try:
        info = ticker.info or {}
    except Exception as exc:
        info = {}
        fetched_warnings.append(f"Could not retrieve ticker.info: {exc}")

    def _info_field(keys: list[str], label: str) -> float | None:
        for k in keys:
            val = info.get(k)
            if val is not None:
                return _safe_float(val)
        fetched_warnings.append(f"Could not find market data field '{label}' — tried: {keys}")
        return None

    market_data["current_price"] = _info_field(
        ["currentPrice", "regularMarketPrice", "previousClose"], "current_price"
    )
    market_data["shares_outstanding"] = _info_field(
        ["sharesOutstanding", "impliedSharesOutstanding"], "shares_outstanding"
    )
    market_data["market_cap"] = _info_field(
        ["marketCap"], "market_cap"
    )
    market_data["beta"] = _info_field(
        ["beta", "beta3Year"], "beta"
    )

    # ------------------------------------------------------------------
    # Assemble result
    # ------------------------------------------------------------------
    return {
        "ticker": ticker_symbol,
        "income_statement": income_data,
        "balance_sheet": balance_data,
        "cash_flow_statement": cashflow_data,
        "market_data": market_data,
        "warnings": fetched_warnings,
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def _fmt(value: Any) -> str:
    """Format a number for display (billions with 3 dp, or plain float)."""
    if value is None:
        return "N/A"
    if abs(value) >= 1e9:
        return f"${value / 1e9:.3f}B"
    if abs(value) >= 1e6:
        return f"${value / 1e6:.3f}M"
    return f"{value:,.4f}"


def print_financial_data(data: dict[str, Any]) -> None:
    """Pretty-print the output of fetch_financial_data."""
    ticker = data.get("ticker", "?")
    print(f"\n{'='*60}")
    print(f"  Financial Data — {ticker}")
    print(f"{'='*60}")

    sections = [
        ("INCOME STATEMENT", data.get("income_statement", {})),
        ("BALANCE SHEET",    data.get("balance_sheet", {})),
        ("CASH FLOW STATEMENT", data.get("cash_flow_statement", {})),
    ]

    for section_name, section_data in sections:
        print(f"\n--- {section_name} ---")
        for item, year_dict in section_data.items():
            print(f"  {item}:")
            if year_dict is None:
                print("    N/A")
            else:
                for year, val in sorted(year_dict.items()):
                    print(f"    {year}: {_fmt(val)}")

    print("\n--- MARKET DATA ---")
    for key, val in data.get("market_data", {}).items():
        print(f"  {key}: {_fmt(val)}")

    warnings = data.get("warnings", [])
    if warnings:
        print(f"\n--- WARNINGS ({len(warnings)}) ---")
        for w in warnings:
            print(f"  [!] {w}")
    else:
        print("\n  No warnings — all fields retrieved successfully.")

    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = fetch_financial_data("AAPL")
    print_financial_data(result)
    # Also print the raw dict for inspection
    import pprint
    print("Raw dictionary:")
    pprint.pprint(result, width=100, sort_dicts=False)
