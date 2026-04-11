import pytest
import pandas as pd
from unittest.mock import MagicMock

from cbrapi.rates import get_key_rate, get_ibor


KEY_RATE_XML = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <KR>
    <DateMet>2023-01-01T00:00:00</DateMet>
    <Rate>7.5</Rate>
    <id>1</id>
    <rowOrder>0</rowOrder>
    <vol>0</vol>
  </KR>
  <KR>
    <DateMet>2023-06-01T00:00:00</DateMet>
    <Rate>8.5</Rate>
    <id>2</id>
    <rowOrder>1</rowOrder>
    <vol>0</vol>
  </KR>
</root>"""

# One row per (date, p1). Uses p1 as the rate-type code.
IBOR_XML = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <MKR>
    <DateMet>2023-01-31T00:00:00</DateMet>
    <p1>1</p1>
    <d1>5.50</d1>
    <d7>5.80</d7>
    <d30>6.00</d30>
    <d90>6.20</d90>
    <id>1</id>
    <rowOrder>0</rowOrder>
    <vol>100</vol>
  </MKR>
  <MKR>
    <DateMet>2023-01-31T00:00:00</DateMet>
    <p1>2</p1>
    <d1>5.30</d1>
    <d7>5.60</d7>
    <d30>5.90</d30>
    <d90>6.10</d90>
    <id>2</id>
    <rowOrder>1</rowOrder>
    <vol>100</vol>
  </MKR>
  <MKR>
    <DateMet>2023-02-28T00:00:00</DateMet>
    <p1>1</p1>
    <d1>5.60</d1>
    <d7>5.90</d7>
    <d30>6.10</d30>
    <d90>6.30</d90>
    <id>3</id>
    <rowOrder>2</rowOrder>
    <vol>110</vol>
  </MKR>
  <MKR>
    <DateMet>2023-02-28T00:00:00</DateMet>
    <p1>2</p1>
    <d1>5.40</d1>
    <d7>5.70</d7>
    <d30>6.00</d30>
    <d90>6.20</d90>
    <id>4</id>
    <rowOrder>3</rowOrder>
    <vol>110</vol>
  </MKR>
</root>"""

EMPTY_XML = "<?xml version='1.0'?><root/>"


# ---------------------------------------------------------------------------
# get_key_rate
# ---------------------------------------------------------------------------


class TestGetKeyRate:
    def _mock(self, mocker, xml=KEY_RATE_XML):
        mock_client = MagicMock()
        mock_client.service.KeyRate.return_value = xml
        mocker.patch("cbrapi.rates.make_cbr_client", return_value=mock_client)

    def test_returns_series(self, mocker):
        self._mock(mocker)
        result = get_key_rate("2023-01-01", "2023-06-30")
        assert isinstance(result, pd.Series)

    def test_series_named_key_rate(self, mocker):
        self._mock(mocker)
        result = get_key_rate("2023-01-01", "2023-06-30")
        assert result.name == "KEY_RATE"

    def test_values_are_floats(self, mocker):
        self._mock(mocker)
        result = get_key_rate("2023-01-01", "2023-06-30")
        assert result.dtype == float

    def test_first_value_correct(self, mocker):
        self._mock(mocker)
        result = get_key_rate("2023-01-01", "2023-06-30")
        assert result.iloc[0] == pytest.approx(7.5)

    def test_has_period_index(self, mocker):
        self._mock(mocker)
        result = get_key_rate("2023-01-01", "2023-06-30")
        assert isinstance(result.index, pd.PeriodIndex)

    def test_gaps_forward_filled(self, mocker):
        self._mock(mocker)
        result = get_key_rate("2023-01-01", "2023-06-30")
        # 2023-01-01 to 2023-06-01 has many days; both values should be present
        assert len(result) > 2

    def test_monthly_period(self, mocker):
        self._mock(mocker)
        result = get_key_rate("2023-01-01", "2023-06-30", period="M")
        assert isinstance(result, pd.Series)

    def test_empty_xml_returns_empty_series(self, mocker):
        self._mock(mocker, EMPTY_XML)
        result = get_key_rate("2023-01-01", "2023-06-30")
        assert result.empty

    def test_uses_default_dates(self, mocker):
        self._mock(mocker)
        result = get_key_rate()
        assert isinstance(result, pd.Series)

    def test_service_called(self, mocker):
        mock_client = MagicMock()
        mock_client.service.KeyRate.return_value = KEY_RATE_XML
        mocker.patch("cbrapi.rates.make_cbr_client", return_value=mock_client)
        get_key_rate("2023-01-01", "2023-06-30")
        assert mock_client.service.KeyRate.called


# ---------------------------------------------------------------------------
# get_ibor
# ---------------------------------------------------------------------------


class TestGetIbor:
    def _mock(self, mocker, xml=IBOR_XML):
        mock_client = MagicMock()
        mock_client.service.MKR.return_value = xml
        mocker.patch("cbrapi.rates.make_cbr_client", return_value=mock_client)

    def test_returns_dataframe(self, mocker):
        self._mock(mocker)
        result = get_ibor("2023-01-01", "2023-03-31")
        assert isinstance(result, pd.DataFrame)

    def test_has_multiindex_columns(self, mocker):
        self._mock(mocker)
        result = get_ibor("2023-01-01", "2023-03-31")
        assert isinstance(result.columns, pd.MultiIndex)

    def test_tenor_columns_renamed(self, mocker):
        self._mock(mocker)
        result = get_ibor("2023-01-01", "2023-03-31")
        level_0_values = result.columns.get_level_values(0).unique()
        assert "D1" in level_0_values

    def test_rate_type_columns_renamed(self, mocker):
        self._mock(mocker)
        result = get_ibor("2023-01-01", "2023-03-31")
        level_1_values = result.columns.get_level_values(1).unique()
        assert "MIBID_RUB" in level_1_values
        assert "MIBOR_RUB" in level_1_values

    def test_has_period_index(self, mocker):
        self._mock(mocker)
        result = get_ibor("2023-01-01", "2023-03-31")
        assert isinstance(result.index, pd.PeriodIndex)

    def test_empty_xml_returns_empty(self, mocker):
        self._mock(mocker, EMPTY_XML)
        result = get_ibor("2023-01-01", "2023-03-31")
        assert result.empty

    def test_uses_default_dates(self, mocker):
        self._mock(mocker)
        result = get_ibor()
        assert isinstance(result, pd.DataFrame)

    def test_service_called(self, mocker):
        mock_client = MagicMock()
        mock_client.service.MKR.return_value = IBOR_XML
        mocker.patch("cbrapi.rates.make_cbr_client", return_value=mock_client)
        get_ibor("2023-01-01", "2023-03-31")
        assert mock_client.service.MKR.called
