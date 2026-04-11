import pytest
import pandas as pd
from unittest.mock import MagicMock

from cbrapi.ruonia import (
    get_ruonia_overnight,
    get_ruonia_index,
    get_roisfix,
    get_ruonia_ts,
)


RUONIA_OVERNIGHT_XML = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <ro>
    <DateMet>2023-01-03T00:00:00</DateMet>
    <ruo>7.50</ruo>
    <id>1</id>
    <rowOrder>0</rowOrder>
    <vol>0</vol>
  </ro>
  <ro>
    <DateMet>2023-01-10T00:00:00</DateMet>
    <ruo>7.60</ruo>
    <id>2</id>
    <rowOrder>1</rowOrder>
    <vol>0</vol>
  </ro>
</root>"""

RUONIA_INDEX_XML = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <ra>
    <DateMet>2023-01-03T00:00:00</DateMet>
    <RUONIA_Index>105.25</RUONIA_Index>
    <R1W>7.20</R1W>
    <R2W>7.30</R2W>
    <R1M>7.40</R1M>
    <id>1</id>
    <rowOrder>0</rowOrder>
    <vol>0</vol>
  </ra>
  <ra>
    <DateMet>2023-01-10T00:00:00</DateMet>
    <RUONIA_Index>105.50</RUONIA_Index>
    <R1W>7.25</R1W>
    <R2W>7.35</R2W>
    <R1M>7.45</R1M>
    <id>2</id>
    <rowOrder>1</rowOrder>
    <vol>0</vol>
  </ra>
</root>"""

ROISFIX_XML = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <rf>
    <DateMet>2023-01-03T00:00:00</DateMet>
    <R1W>7.10</R1W>
    <R2W>7.20</R2W>
    <R1M>7.30</R1M>
    <R2M>7.40</R2M>
    <R3M>7.50</R3M>
    <R6M>7.70</R6M>
    <id>1</id>
    <rowOrder>0</rowOrder>
    <vol>0</vol>
  </rf>
  <rf>
    <DateMet>2023-01-10T00:00:00</DateMet>
    <R1W>7.15</R1W>
    <R2W>7.25</R2W>
    <R1M>7.35</R1M>
    <R2M>7.45</R2M>
    <R3M>7.55</R3M>
    <R6M>7.75</R6M>
    <id>2</id>
    <rowOrder>1</rowOrder>
    <vol>0</vol>
  </rf>
</root>"""

EMPTY_XML = "<?xml version='1.0'?><root/>"


# ---------------------------------------------------------------------------
# get_ruonia_overnight
# ---------------------------------------------------------------------------


class TestGetRuoniaOvernight:
    def _mock(self, mocker, xml=RUONIA_OVERNIGHT_XML):
        mock_client = MagicMock()
        mock_client.service.Ruonia.return_value = xml
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)

    def test_returns_series(self, mocker):
        self._mock(mocker)
        result = get_ruonia_overnight("2023-01-01", "2023-01-15")
        assert isinstance(result, pd.Series)

    def test_series_named_ruonia_overnight(self, mocker):
        self._mock(mocker)
        result = get_ruonia_overnight("2023-01-01", "2023-01-15")
        assert result.name == "RUONIA_OVERNIGHT"

    def test_values_divided_by_100(self, mocker):
        self._mock(mocker)
        result = get_ruonia_overnight("2023-01-01", "2023-01-15")
        # XML has 7.50 → should become 0.075
        assert result.iloc[0] == pytest.approx(0.075)

    def test_has_period_index(self, mocker):
        self._mock(mocker)
        result = get_ruonia_overnight("2023-01-01", "2023-01-15")
        assert isinstance(result.index, pd.PeriodIndex)

    def test_gaps_forward_filled(self, mocker):
        self._mock(mocker)
        result = get_ruonia_overnight("2023-01-01", "2023-01-15")
        assert len(result) >= 8  # 2023-01-03 to 2023-01-10 padded

    def test_monthly_period(self, mocker):
        two_month_xml = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <ro><DateMet>2023-01-03T00:00:00</DateMet><ruo>7.50</ruo><id>1</id><rowOrder>0</rowOrder><vol>0</vol></ro>
  <ro><DateMet>2023-02-03T00:00:00</DateMet><ruo>7.60</ruo><id>2</id><rowOrder>1</rowOrder><vol>0</vol></ro>
</root>"""
        mock_client = MagicMock()
        mock_client.service.Ruonia.return_value = two_month_xml
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)
        result = get_ruonia_overnight("2023-01-01", "2023-02-28", period="M")
        assert isinstance(result, pd.Series)

    def test_empty_xml_returns_empty(self, mocker):
        self._mock(mocker, EMPTY_XML)
        result = get_ruonia_overnight("2023-01-01", "2023-01-15")
        assert result.empty

    def test_service_called(self, mocker):
        mock_client = MagicMock()
        mock_client.service.Ruonia.return_value = RUONIA_OVERNIGHT_XML
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)
        get_ruonia_overnight("2023-01-01", "2023-01-15")
        assert mock_client.service.Ruonia.called


# ---------------------------------------------------------------------------
# get_ruonia_index
# ---------------------------------------------------------------------------


class TestGetRuoniaIndex:
    def _mock(self, mocker, xml=RUONIA_INDEX_XML):
        mock_client = MagicMock()
        mock_client.service.RuoniaSV.return_value = xml
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)

    def test_returns_dataframe(self, mocker):
        self._mock(mocker)
        result = get_ruonia_index("2023-01-01", "2023-01-15")
        assert isinstance(result, pd.DataFrame)

    def test_has_all_columns(self, mocker):
        self._mock(mocker)
        result = get_ruonia_index("2023-01-01", "2023-01-15")
        expected = {"RUONIA_INDEX", "RUONIA_AVG_1M", "RUONIA_AVG_3M", "RUONIA_AVG_6M"}
        assert set(result.columns) == expected

    def test_index_value_correct(self, mocker):
        self._mock(mocker)
        result = get_ruonia_index("2023-01-01", "2023-01-15")
        assert result["RUONIA_INDEX"].iloc[0] == pytest.approx(105.25)

    def test_has_period_index(self, mocker):
        self._mock(mocker)
        result = get_ruonia_index("2023-01-01", "2023-01-15")
        assert isinstance(result.index, pd.PeriodIndex)

    def test_empty_xml_returns_empty(self, mocker):
        self._mock(mocker, EMPTY_XML)
        result = get_ruonia_index("2023-01-01", "2023-01-15")
        assert result.empty


# ---------------------------------------------------------------------------
# get_roisfix
# ---------------------------------------------------------------------------


class TestGetRoisfix:
    def _mock(self, mocker, xml=ROISFIX_XML):
        mock_client = MagicMock()
        mock_client.service.ROISfix.return_value = xml
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)

    def test_returns_dataframe(self, mocker):
        self._mock(mocker)
        result = get_roisfix("2023-01-01", "2023-01-15")
        assert isinstance(result, pd.DataFrame)

    def test_has_all_tenor_columns(self, mocker):
        self._mock(mocker)
        result = get_roisfix("2023-01-01", "2023-01-15")
        expected = {
            "RATE_1_WEEK",
            "RATE_2_WEEK",
            "RATE_1_MONTH",
            "RATE_2_MONTH",
            "RATE_3_MONTH",
            "RATE_6_MONTH",
        }
        assert set(result.columns) == expected

    def test_values_are_numeric(self, mocker):
        self._mock(mocker)
        result = get_roisfix("2023-01-01", "2023-01-15")
        assert result["RATE_1_WEEK"].dtype == float

    def test_rate_1_week_value(self, mocker):
        self._mock(mocker)
        result = get_roisfix("2023-01-01", "2023-01-15")
        assert result["RATE_1_WEEK"].iloc[0] == pytest.approx(7.10)

    def test_has_period_index(self, mocker):
        self._mock(mocker)
        result = get_roisfix("2023-01-01", "2023-01-15")
        assert isinstance(result.index, pd.PeriodIndex)

    def test_monthly_period(self, mocker):
        self._mock(mocker)
        result = get_roisfix("2023-01-01", "2023-01-31", period="M")
        assert isinstance(result, pd.DataFrame)

    def test_empty_xml_returns_empty(self, mocker):
        self._mock(mocker, EMPTY_XML)
        result = get_roisfix("2023-01-01", "2023-01-15")
        assert result.empty

    def test_service_called(self, mocker):
        mock_client = MagicMock()
        mock_client.service.ROISfix.return_value = ROISFIX_XML
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)
        get_roisfix("2023-01-01", "2023-01-15")
        assert mock_client.service.ROISfix.called


# ---------------------------------------------------------------------------
# get_ruonia_ts (router function)
# ---------------------------------------------------------------------------


class TestGetRuoniaTs:
    def _mock_index(self, mocker):
        mock_client = MagicMock()
        mock_client.service.RuoniaSV.return_value = RUONIA_INDEX_XML
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)

    def _mock_overnight(self, mocker):
        mock_client = MagicMock()
        mock_client.service.Ruonia.return_value = RUONIA_OVERNIGHT_XML
        mocker.patch("cbrapi.ruonia.make_cbr_client", return_value=mock_client)

    def test_ruonia_indx_routes_to_index(self, mocker):
        self._mock_index(mocker)
        result = get_ruonia_ts("RUONIA.INDX", "2023-01-01", "2023-01-15")
        assert isinstance(result, pd.Series)

    def test_avg_1m_rate_divides_by_100(self, mocker):
        self._mock_index(mocker)
        result = get_ruonia_ts("RUONIA_AVG_1M.RATE", "2023-01-01", "2023-01-15")
        # XML has R1W=7.20 → after /100 → 0.072
        assert result.iloc[0] == pytest.approx(0.072)

    def test_avg_3m_rate(self, mocker):
        self._mock_index(mocker)
        result = get_ruonia_ts("RUONIA_AVG_3M.RATE", "2023-01-01", "2023-01-15")
        assert result.iloc[0] == pytest.approx(0.073)

    def test_avg_6m_rate(self, mocker):
        self._mock_index(mocker)
        result = get_ruonia_ts("RUONIA_AVG_6M.RATE", "2023-01-01", "2023-01-15")
        assert result.iloc[0] == pytest.approx(0.074)

    def test_other_symbol_routes_to_overnight(self, mocker):
        self._mock_overnight(mocker)
        result = get_ruonia_ts("RUONIA", "2023-01-01", "2023-01-15")
        assert isinstance(result, pd.Series)
        assert result.name == "RUONIA_OVERNIGHT"

    def test_ruonia_indx_not_divided_by_100(self, mocker):
        self._mock_index(mocker)
        result = get_ruonia_ts("RUONIA.INDX", "2023-01-01", "2023-01-15")
        # RUONIA_INDEX value should be 105.25, not 1.0525
        assert result.iloc[0] == pytest.approx(105.25)
