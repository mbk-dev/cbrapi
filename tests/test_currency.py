import pytest
import pandas as pd
from unittest.mock import MagicMock

from cbrapi.currency import get_currencies_list, get_currency_code, get_time_series

# XML returned by EnumValutesXML — must be bytes (used with BytesIO for daily)
CURRENCIES_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ValuteData>
  <EnumValutes>
    <Vcode>R01235</Vcode>
    <Vnom>1</Vnom>
    <VcharCode>USD</VcharCode>
    <VunitRate>1</VunitRate>
  </EnumValutes>
  <EnumValutes>
    <Vcode>R01239</Vcode>
    <Vnom>1</Vnom>
    <VcharCode>EUR</VcharCode>
    <VunitRate>1</VunitRate>
  </EnumValutes>
</ValuteData>"""

# XML returned by GetCursDynamic — must have exactly: rowOrder, id, Vnom, Vcode, CursDate, Vcurs
RATES_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ValuteData>
  <ValuteCursDynamic>
    <rowOrder>0</rowOrder>
    <id>R01235</id>
    <Vnom>1</Vnom>
    <Vcode>R01235</Vcode>
    <CursDate>2023-01-03T00:00:00</CursDate>
    <Vcurs>70.3271</Vcurs>
  </ValuteCursDynamic>
  <ValuteCursDynamic>
    <rowOrder>1</rowOrder>
    <id>R01235</id>
    <Vnom>1</Vnom>
    <Vcode>R01235</Vcode>
    <CursDate>2023-01-10T00:00:00</CursDate>
    <Vcurs>71.0000</Vcurs>
  </ValuteCursDynamic>
</ValuteData>"""

EMPTY_XML = b"<?xml version='1.0'?><root/>"


def _make_mock_client(xml=CURRENCIES_XML):
    mock_client = MagicMock()
    mock_client.service.EnumValutesXML.return_value = xml
    return mock_client


# ---------------------------------------------------------------------------
# get_currencies_list
# ---------------------------------------------------------------------------


class TestGetCurrenciesList:
    def test_returns_dataframe(self, mocker):
        mock_client = _make_mock_client()
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)

        result = get_currencies_list()
        assert isinstance(result, pd.DataFrame)

    def test_contains_expected_columns(self, mocker):
        mock_client = _make_mock_client()
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)

        result = get_currencies_list()
        assert "VcharCode" in result.columns
        assert "Vcode" in result.columns

    def test_combines_daily_and_monthly(self, mocker):
        mock_client = _make_mock_client()
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)

        result = get_currencies_list()
        # daily + monthly both return 2 rows → concat gives 4
        assert len(result) == 4

    def test_contains_usd_and_eur(self, mocker):
        mock_client = _make_mock_client()
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)

        result = get_currencies_list()
        assert "USD" in result["VcharCode"].values
        assert "EUR" in result["VcharCode"].values


# ---------------------------------------------------------------------------
# get_currency_code
# ---------------------------------------------------------------------------


class TestGetCurrencyCode:
    def test_returns_correct_code(self, mocker, currencies_df):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        assert get_currency_code("USD") == "R01235"

    def test_eur_code(self, mocker, currencies_df):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        assert get_currency_code("EUR") == "R01239"

    def test_unknown_ticker_raises(self, mocker, currencies_df):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        with pytest.raises(ValueError):
            get_currency_code("GBP")

    def test_dot_in_ticker_raises(self, mocker, currencies_df):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        with pytest.raises(ValueError, match="dots"):
            get_currency_code("U.SD")


# ---------------------------------------------------------------------------
# get_time_series
# ---------------------------------------------------------------------------


class TestGetTimeSeries:
    def _setup_mocks(self, mocker, currencies_df, rate_xml=RATES_XML):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        mock_client = MagicMock()
        mock_client.service.GetCursDynamic.return_value = rate_xml
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)

    def test_returns_series(self, mocker, currencies_df):
        self._setup_mocks(mocker, currencies_df)
        result = get_time_series("USD", "2023-01-01", "2023-01-15")
        assert isinstance(result, pd.Series)

    def test_series_named_after_symbol(self, mocker, currencies_df):
        self._setup_mocks(mocker, currencies_df)
        result = get_time_series("USD", "2023-01-01", "2023-01-15")
        assert result.name == "USD"

    def test_values_are_floats(self, mocker, currencies_df):
        self._setup_mocks(mocker, currencies_df)
        result = get_time_series("USD", "2023-01-01", "2023-01-15")
        assert result.dtype == float

    def test_covers_requested_date_range(self, mocker, currencies_df):
        self._setup_mocks(mocker, currencies_df)
        result = get_time_series("USD", "2023-01-03", "2023-01-10")
        assert len(result) >= 2

    def test_monthly_period_resamples(self, mocker, currencies_df):
        self._setup_mocks(mocker, currencies_df)
        result = get_time_series("USD", "2023-01-01", "2023-01-31", period="M")
        assert isinstance(result, pd.Series)
        assert len(result) >= 1

    def test_inverse_rub_pair(self, mocker, currencies_df):
        """RUBUSD should return 1/rate of the USD/RUB series."""
        self._setup_mocks(mocker, currencies_df)
        direct = get_time_series("USD", "2023-01-03", "2023-01-03")
        self._setup_mocks(mocker, currencies_df)
        inverse = get_time_series("RUBUSD", "2023-01-03", "2023-01-03")
        assert inverse.iloc[0] == pytest.approx(1.0 / direct.iloc[0])

    def test_empty_xml_returns_empty_series(self, mocker, currencies_df):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        mock_client = MagicMock()
        mock_client.service.GetCursDynamic.return_value = EMPTY_XML
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)
        result = get_time_series("USD", "2023-01-01", "2023-01-31")
        assert isinstance(result, pd.Series)
        assert result.empty

    def test_unexpected_columns_raise(self, mocker, currencies_df):
        bad_xml = b"""<?xml version="1.0"?>
        <ValuteData>
          <ValuteCursDynamic>
            <unexpected_col>foo</unexpected_col>
            <CursDate>2023-01-01T00:00:00</CursDate>
          </ValuteCursDynamic>
        </ValuteData>"""
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        mock_client = MagicMock()
        mock_client.service.GetCursDynamic.return_value = bad_xml
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)
        with pytest.raises(ValueError, match="CBR data has different columns"):
            get_time_series("USD", "2023-01-01", "2023-01-31")

    def test_cross_course_symbol_raises(self, mocker, currencies_df):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        with pytest.raises(ValueError, match="cross courses"):
            get_time_series("USDEUR", "2023-01-01", "2023-01-31")


# ---------------------------------------------------------------------------
# get_time_series — successor currency codes
# ---------------------------------------------------------------------------

# Real CBR shape: GetCursDynamic("R01100") (Bulgarian Lev) lists the 1999-07-01
# redenomination day twice — the last quote of the old code (Vnom=1000) and the
# first quote of the successor code R01100Z (Vnom=1).
REDENOMINATION_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ValuteData>
  <ValuteCursDynamic>
    <rowOrder>0</rowOrder>
    <id>R01100</id>
    <Vnom>1000</Vnom>
    <Vcode>R01100</Vcode>
    <CursDate>1999-06-01T00:00:00</CursDate>
    <Vcurs>13.1000</Vcurs>
  </ValuteCursDynamic>
  <ValuteCursDynamic>
    <rowOrder>1</rowOrder>
    <id>R01100</id>
    <Vnom>1000</Vnom>
    <Vcode>R01100</Vcode>
    <CursDate>1999-07-01T00:00:00</CursDate>
    <Vcurs>12.8900</Vcurs>
  </ValuteCursDynamic>
  <ValuteCursDynamic>
    <rowOrder>2</rowOrder>
    <id>R01100Z</id>
    <Vnom>1</Vnom>
    <Vcode>R01100Z</Vcode>
    <CursDate>1999-07-01T00:00:00</CursDate>
    <Vcurs>12.7700</Vcurs>
  </ValuteCursDynamic>
  <ValuteCursDynamic>
    <rowOrder>3</rowOrder>
    <id>R01100</id>
    <Vnom>1</Vnom>
    <Vcode>R01100</Vcode>
    <CursDate>1999-08-01T00:00:00</CursDate>
    <Vcurs>13.2700</Vcurs>
  </ValuteCursDynamic>
</ValuteData>"""

# Most of the Romanian Leu history comes back under the successor code R01585F,
# not under the requested R01585 — successor rows carry real data.
SUCCESSOR_HISTORY_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ValuteData>
  <ValuteCursDynamic>
    <rowOrder>0</rowOrder>
    <id>R01585</id>
    <Vnom>1000</Vnom>
    <Vcode>R01585</Vcode>
    <CursDate>2005-06-01T00:00:00</CursDate>
    <Vcurs>0.9500</Vcurs>
  </ValuteCursDynamic>
  <ValuteCursDynamic>
    <rowOrder>1</rowOrder>
    <id>R01585F</id>
    <Vnom>1</Vnom>
    <Vcode>R01585F</Vcode>
    <CursDate>2005-07-01T00:00:00</CursDate>
    <Vcurs>9.7000</Vcurs>
  </ValuteCursDynamic>
  <ValuteCursDynamic>
    <rowOrder>2</rowOrder>
    <id>R01585F</id>
    <Vnom>1</Vnom>
    <Vcode>R01585F</Vcode>
    <CursDate>2005-08-01T00:00:00</CursDate>
    <Vcurs>9.8000</Vcurs>
  </ValuteCursDynamic>
</ValuteData>"""

# Same code, same date, twice — not a code transition, so it must still raise.
SAME_CODE_DUPLICATE_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<ValuteData>
  <ValuteCursDynamic>
    <rowOrder>0</rowOrder>
    <id>R01235</id>
    <Vnom>1</Vnom>
    <Vcode>R01235</Vcode>
    <CursDate>2023-01-03T00:00:00</CursDate>
    <Vcurs>70.3271</Vcurs>
  </ValuteCursDynamic>
  <ValuteCursDynamic>
    <rowOrder>1</rowOrder>
    <id>R01235</id>
    <Vnom>1</Vnom>
    <Vcode>R01235</Vcode>
    <CursDate>2023-01-03T00:00:00</CursDate>
    <Vcurs>71.0000</Vcurs>
  </ValuteCursDynamic>
</ValuteData>"""


@pytest.fixture
def bgn_currencies_df():
    """CBR pads Vcode to a fixed width, so the live service returns 'R01100    '."""
    return pd.DataFrame(
        {
            "Vcode": ["R01100              "],
            "Vnom": [1],
            "VcharCode": ["BGN"],
            "VunitRate": [1],
        }
    )


@pytest.fixture
def ron_currencies_df():
    return pd.DataFrame(
        {
            "Vcode": ["R01585              "],
            "Vnom": [1],
            "VcharCode": ["ROL"],
            "VunitRate": [1],
        }
    )


class TestSuccessorCurrencyCodes:
    def _setup_mocks(self, mocker, currencies_df, rate_xml):
        mocker.patch("cbrapi.currency.get_currencies_list", return_value=currencies_df)
        mock_client = MagicMock()
        mock_client.service.GetCursDynamic.return_value = rate_xml
        mocker.patch("cbrapi.currency.make_cbr_client", return_value=mock_client)

    def test_redenomination_day_is_not_duplicated(self, mocker, bgn_currencies_df):
        """Before the fix the doubled date raised 'CBR returned duplicate dates',
        which 500'd every request for BGN history spanning the redenomination."""
        self._setup_mocks(mocker, bgn_currencies_df, REDENOMINATION_XML)

        result = get_time_series("BGN", "1999-06-01", "1999-08-01")

        assert result.index.is_unique
        # the successor quote wins: the rest of the series is in the new lev
        assert result.loc[pd.Period("1999-07-01", "D")] == pytest.approx(12.77)
        assert result.loc[pd.Period("1999-08-01", "D")] == pytest.approx(13.27)

    def test_successor_code_history_is_kept(self, mocker, ron_currencies_df):
        """Successor-code rows are real history and must never be filtered out."""
        self._setup_mocks(mocker, ron_currencies_df, SUCCESSOR_HISTORY_XML)

        result = get_time_series("ROL", "2005-06-01", "2005-08-01")

        assert result.loc[pd.Period("2005-06-01", "D")] == pytest.approx(0.95 / 1000)
        assert result.loc[pd.Period("2005-07-01", "D")] == pytest.approx(9.7)
        assert result.loc[pd.Period("2005-08-01", "D")] == pytest.approx(9.8)

    def test_duplicate_date_under_one_code_still_raises(self, mocker, currencies_df):
        """A date repeated under a single code is a real anomaly, not a
        redenomination — the tripwire must stay armed."""
        self._setup_mocks(mocker, currencies_df, SAME_CODE_DUPLICATE_XML)

        with pytest.raises(ValueError, match="duplicate dates"):
            get_time_series("USD", "2023-01-01", "2023-01-31")

    def test_ordinary_answer_is_untouched(self, mocker, currencies_df):
        self._setup_mocks(mocker, currencies_df, RATES_XML)

        result = get_time_series("USD", "2023-01-03", "2023-01-10")

        assert result.loc[pd.Period("2023-01-03", "D")] == pytest.approx(70.3271)
        assert result.loc[pd.Period("2023-01-10", "D")] == pytest.approx(71.0)
