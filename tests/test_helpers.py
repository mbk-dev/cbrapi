import pytest
import pandas as pd
from datetime import datetime, date

from cbrapi.helpers import (
    pad_missing_periods,
    calculate_inverse_rate,
    set_datetime_index,
    remove_unnecessary_columns,
    unstack_groups,
    column_rename,
    normalize_data,
    guess_date,
    check_ticker_code,
    check_symbol_ts,
)

# ---------------------------------------------------------------------------
# pad_missing_periods
# ---------------------------------------------------------------------------


class TestPadMissingPeriods:
    def test_fills_gaps_with_forward_fill(self):
        idx = pd.PeriodIndex(["2023-01-01", "2023-01-03"], freq="D")
        s = pd.Series([1.0, 3.0], index=idx)
        result = pad_missing_periods(s)
        assert len(result) == 3
        assert result["2023-01-02"] == pytest.approx(1.0)

    def test_empty_series_returned_unchanged(self):
        s = pd.Series(dtype=float)
        result = pad_missing_periods(s)
        assert result.empty

    def test_extends_to_end_date(self):
        idx = pd.PeriodIndex(["2023-01-01"], freq="D")
        s = pd.Series([5.0], index=idx)
        result = pad_missing_periods(s, end_date=date(2023, 1, 4))
        assert len(result) == 4
        assert all(v == pytest.approx(5.0) for v in result)

    def test_end_date_before_last_index_has_no_effect(self):
        idx = pd.PeriodIndex(["2023-01-01", "2023-01-05"], freq="D")
        s = pd.Series([1.0, 5.0], index=idx)
        result = pad_missing_periods(s, end_date=date(2023, 1, 3))
        assert result.index[-1] == pd.Period("2023-01-05", freq="D")

    def test_preserves_index_name(self):
        idx = pd.PeriodIndex(["2023-01-01", "2023-01-03"], freq="D", name="date")
        s = pd.Series([1.0, 3.0], index=idx)
        result = pad_missing_periods(s)
        assert result.index.name == "date"

    def test_works_with_dataframe(self):
        idx = pd.PeriodIndex(["2023-01-01", "2023-01-03"], freq="D")
        df = pd.DataFrame({"A": [1.0, 3.0], "B": [2.0, 4.0]}, index=idx)
        result = pad_missing_periods(df)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# calculate_inverse_rate
# ---------------------------------------------------------------------------


class TestCalculateInverseRate:
    def test_inverts_values(self):
        s = pd.Series([2.0, 4.0, 0.5])
        result = calculate_inverse_rate(s)
        assert result.iloc[0] == pytest.approx(0.5)
        assert result.iloc[1] == pytest.approx(0.25)
        assert result.iloc[2] == pytest.approx(2.0)

    def test_returns_series(self):
        s = pd.Series([1.0])
        assert isinstance(calculate_inverse_rate(s), pd.Series)


# ---------------------------------------------------------------------------
# set_datetime_index
# ---------------------------------------------------------------------------


class TestSetDatetimeIndex:
    def test_converts_datemet_column(self):
        df = pd.DataFrame(
            {"DateMet": ["2023-01-01T00:00:00", "2023-01-02T00:00:00"], "val": [1, 2]}
        )
        result = set_datetime_index(df)
        assert isinstance(result.index, pd.DatetimeIndex)
        assert "DateMet" not in result.columns

    def test_strips_time_component(self):
        df = pd.DataFrame({"DateMet": ["2023-06-15T12:30:00"], "val": [1]})
        result = set_datetime_index(df)
        assert result.index[0] == pd.Timestamp("2023-06-15")

    def test_already_has_datetime_index(self):
        idx = pd.DatetimeIndex(["2023-01-01"])
        df = pd.DataFrame({"val": [1]}, index=idx)
        result = set_datetime_index(df)
        assert isinstance(result.index, pd.DatetimeIndex)


# ---------------------------------------------------------------------------
# remove_unnecessary_columns
# ---------------------------------------------------------------------------


class TestRemoveUnnecessaryColumns:
    def test_removes_known_columns(self):
        df = pd.DataFrame(
            {
                "id": [1],
                "rowOrder": [0],
                "vol": [0],
                "DateUpdate": ["x"],
                "value": [1.0],
            }
        )
        result = remove_unnecessary_columns(df)
        assert list(result.columns) == ["value"]

    def test_ignores_missing_columns(self):
        df = pd.DataFrame({"value": [1.0]})
        result = remove_unnecessary_columns(df)
        assert list(result.columns) == ["value"]


# ---------------------------------------------------------------------------
# unstack_groups
# ---------------------------------------------------------------------------


class TestUnstackGroups:
    def test_drgmet_unstacks_by_codmet(self):
        idx = pd.DatetimeIndex(["2023-01-01", "2023-01-01", "2023-01-01", "2023-01-01"])
        df = pd.DataFrame(
            {"CodMet": [1, 2, 3, 4], "price": [100.0, 50.0, 200.0, 150.0]},
            index=idx,
        )
        result = unstack_groups(df, "DrgMet")
        assert set(result.columns) == {1, 2, 3, 4}

    def test_mkr_unstacks_by_p1(self):
        idx = pd.DatetimeIndex(["2023-01-31", "2023-01-31"])
        df = pd.DataFrame(
            {
                "p1": [1, 2],
                "d1": [5.5, 5.3],
                "d7": [5.8, 5.6],
                "d30": [6.0, 5.9],
                "d90": [6.2, 6.1],
            },
            index=idx,
        )
        result = unstack_groups(df, "MKR")
        assert isinstance(result.columns, pd.MultiIndex)
        assert "d1" in result.columns.get_level_values(0)

    def test_unknown_symbol_returns_unchanged(self):
        df = pd.DataFrame({"val": [1.0]})
        result = unstack_groups(df, "OTHER")
        assert list(result.columns) == ["val"]


# ---------------------------------------------------------------------------
# column_rename
# ---------------------------------------------------------------------------


class TestColumnRename:
    def test_renames_single_level_columns(self):
        df = pd.DataFrame({"Rate": [7.5], "extra": [1]})
        result = column_rename(df, level_0=None, level_1={"Rate": "KEY_RATE"})
        assert "KEY_RATE" in result.columns

    def test_keeps_only_mapped_columns(self):
        df = pd.DataFrame({"Rate": [7.5], "extra": [1]})
        result = column_rename(df, level_0=None, level_1={"Rate": "KEY_RATE"})
        assert "extra" not in result.columns

    def test_renames_multiindex_level_0(self):
        arrays = [["d1", "d1"], [1, 2]]
        tuples = list(zip(*arrays))
        idx = pd.MultiIndex.from_tuples(tuples)
        df = pd.DataFrame([[1, 2]], columns=idx)
        result = column_rename(df, level_0={"d1": "D1"}, level_1=None)
        assert "D1" in result.columns.get_level_values(0)

    def test_renames_multiindex_level_1(self):
        arrays = [["d1", "d1"], ["1", "2"]]
        tuples = list(zip(*arrays))
        idx = pd.MultiIndex.from_tuples(tuples)
        df = pd.DataFrame([[1, 2]], columns=idx)
        result = column_rename(
            df, level_0=None, level_1={"1": "MIBID_RUB", "2": "MIBOR_RUB"}
        )
        assert "MIBID_RUB" in result.columns.get_level_values(1)


# ---------------------------------------------------------------------------
# guess_date
# ---------------------------------------------------------------------------


class TestGuessDate:
    def test_full_date_format(self):
        result = guess_date("2023-06-15", "2020-01-01")
        assert result == datetime(2023, 6, 15)

    def test_month_only_format(self):
        result = guess_date("2023-06", "2020-01-01")
        assert result == datetime(2023, 6, 1)

    def test_none_uses_default(self):
        result = guess_date(None, "2020-03-15")
        assert result == datetime(2020, 3, 15)

    def test_empty_string_uses_default(self):
        result = guess_date("", "2021-01-01")
        assert result == datetime(2021, 1, 1)


# ---------------------------------------------------------------------------
# check_ticker_code
# ---------------------------------------------------------------------------


class TestCheckTickerCode:
    def test_valid_ticker_returned(self):
        symbol_col = pd.Series(["USD", "EUR", "GBP"])
        assert check_ticker_code("USD", symbol_col) == "USD"

    def test_lowercase_ticker_raises(self):
        # check_ticker_code is case-sensitive — lowercase fails validation
        with pytest.raises(ValueError, match="does not support"):
            check_ticker_code("usd", pd.Series(["USD"]))

    def test_dot_in_ticker_raises(self):
        with pytest.raises(ValueError, match="dots"):
            check_ticker_code("U.SD", pd.Series(["USD"]))

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="3 characters"):
            check_ticker_code("US", pd.Series(["USD"]))

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="3 characters"):
            check_ticker_code("USDT", pd.Series(["USD"]))

    def test_unknown_ticker_raises(self):
        with pytest.raises(ValueError, match="does not support"):
            check_ticker_code("XYZ", pd.Series(["USD", "EUR"]))

    def test_truncates_to_3_chars(self):
        symbol_col = pd.Series(["USD"])
        # "USDRUB" - first 3 chars = "USD", which is in symbol_col
        result = check_ticker_code("USDRUB", symbol_col)
        assert result == "USD"


# ---------------------------------------------------------------------------
# check_symbol_ts
# ---------------------------------------------------------------------------


class TestCheckSymbolTs:
    def test_valid_3char_symbol(self):
        symbol_col = pd.Series(["USD", "EUR"])
        check_symbol_ts("USD", symbol_col)  # no exception

    def test_valid_rub_pair_direct(self):
        symbol_col = pd.Series(["USD", "EUR"])
        check_symbol_ts("USDRUB", symbol_col)  # no exception

    def test_valid_rub_pair_inverse(self):
        symbol_col = pd.Series(["USD", "EUR"])
        check_symbol_ts("RUBUSD", symbol_col)  # no exception

    def test_cross_course_raises(self):
        symbol_col = pd.Series(["USD", "EUR"])
        with pytest.raises(ValueError, match="cross courses"):
            check_symbol_ts("USDEUR", symbol_col)

    def test_dot_in_symbol_raises(self):
        with pytest.raises(ValueError, match="dots"):
            check_symbol_ts("USD.RUB", pd.Series(["USD"]))

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="invalid length"):
            check_symbol_ts("US", pd.Series(["USD"]))

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="invalid length"):
            check_symbol_ts("USDRUBB", pd.Series(["USD"]))

    def test_unknown_3char_symbol_raises(self):
        symbol_col = pd.Series(["USD", "EUR"])
        with pytest.raises(ValueError, match="does not support"):
            check_symbol_ts("GBP", symbol_col)
