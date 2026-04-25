import sys
import types
import unittest


class _TimestampStub:
    def __init__(self, year: int):
        self.year = year


class _SeriesStub:
    def __init__(self, items):
        self._items = items

    def items(self):
        return list(self._items)


class _LocAccessor:
    def __init__(self, rows):
        self._rows = rows

    def __getitem__(self, key):
        return self._rows[key]


class _DataFrameStub:
    def __init__(self, rows):
        self._rows = rows
        self.index = list(rows.keys())
        self.loc = _LocAccessor(rows)

    @property
    def empty(self):
        return not self._rows


sys.modules.setdefault("pandas", types.SimpleNamespace(DataFrame=_DataFrameStub, isna=lambda value: value is None))
sys.modules.setdefault("yfinance", types.SimpleNamespace(Ticker=object))

from assumptions import _compute_ebit_margin
from data_fetcher import _extract_row, _get_statement, INCOME_ALIASES


class _TickerStub:
    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)


class ReviewFixTests(unittest.TestCase):
    def test_balance_statement_does_not_fall_back_to_quarterly(self) -> None:
        quarterly = _DataFrameStub({
            "Total Debt": _SeriesStub([(_TimestampStub(2025), 123.0)]),
        })
        ticker = _TickerStub(balance_sheet=None, quarterly_balance_sheet=quarterly)

        result = _get_statement(ticker, "balance")

        self.assertIsNone(result)

    def test_net_interest_income_is_not_used_as_interest_expense(self) -> None:
        warnings: list[str] = []
        df = _DataFrameStub({
            "Net Interest Income": _SeriesStub([(_TimestampStub(2024), 42.0)]),
        })

        result = _extract_row(df, INCOME_ALIASES["interest_expense"], "interest_expense", warnings)

        self.assertIsNone(result)

    def test_zero_ebit_year_is_included_in_margin_average(self) -> None:
        warnings: list[str] = []
        income_statement = {
            "revenue": {"2023": 100.0, "2024": 100.0},
            "ebit": {"2023": 0.0, "2024": 10.0},
        }

        result = _compute_ebit_margin(income_statement, warnings)

        self.assertEqual(result["status"], "estimated")
        self.assertAlmostEqual(result["annual"]["2023"], 0.0)
        self.assertAlmostEqual(result["annual"]["2024"], 0.1)
        self.assertAlmostEqual(result["value"], 0.05)


if __name__ == "__main__":
    unittest.main()
