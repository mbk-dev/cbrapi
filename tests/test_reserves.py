import pytest
import pandas as pd
from unittest.mock import MagicMock

from cbrapi.reserves import get_mrrf


# One row per date; columns p1-p6 hold reserve components
MRRF_XML = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <mr>
    <DateMet>2023-01-31T00:00:00</DateMet>
    <p1>587000000000</p1>
    <p2>540000000000</p2>
    <p3>490000000000</p3>
    <p4>9000000000</p4>
    <p5>4500000000</p5>
    <p6>33500000000</p6>
    <rowOrder>0</rowOrder>
    <id>1</id>
    <vol>0</vol>
    <DateUpdate>2023-02-14T00:00:00</DateUpdate>
  </mr>
  <mr>
    <DateMet>2023-02-28T00:00:00</DateMet>
    <p1>590000000000</p1>
    <p2>542000000000</p2>
    <p3>492000000000</p3>
    <p4>9100000000</p4>
    <p5>4600000000</p5>
    <p6>34300000000</p6>
    <rowOrder>1</rowOrder>
    <id>2</id>
    <vol>0</vol>
    <DateUpdate>2023-03-14T00:00:00</DateUpdate>
  </mr>
</root>"""

EMPTY_XML = "<?xml version='1.0'?><root/>"


class TestGetMrrf:
    def _mock(self, mocker, xml=MRRF_XML):
        mock_client = MagicMock()
        mock_client.service.mrrf.return_value = xml
        mocker.patch("cbrapi.reserves.make_cbr_client", return_value=mock_client)

    def test_returns_dataframe(self, mocker):
        self._mock(mocker)
        result = get_mrrf("2023-01-01", "2023-03-31")
        assert isinstance(result, pd.DataFrame)

    def test_has_all_reserve_columns(self, mocker):
        self._mock(mocker)
        result = get_mrrf("2023-01-01", "2023-03-31")
        expected = {
            "TOTAL_RESERVES",
            "CURRENCY_RESERVES",
            "FOREIGN_CURRENCY",
            "SDR_ACCOUNT",
            "IMF_RESERVE",
            "MONETARY_GOLD",
        }
        assert set(result.columns) == expected

    def test_values_are_numeric(self, mocker):
        self._mock(mocker)
        result = get_mrrf("2023-01-01", "2023-03-31")
        assert pd.api.types.is_numeric_dtype(result["TOTAL_RESERVES"])

    def test_total_reserves_value(self, mocker):
        self._mock(mocker)
        result = get_mrrf("2023-01-01", "2023-03-31")
        assert result["TOTAL_RESERVES"].iloc[0] == pytest.approx(587_000_000_000.0)

    def test_has_period_index(self, mocker):
        self._mock(mocker)
        result = get_mrrf("2023-01-01", "2023-03-31")
        assert isinstance(result.index, pd.PeriodIndex)

    def test_two_rows_returned(self, mocker):
        self._mock(mocker)
        result = get_mrrf("2023-01-01", "2023-03-31")
        assert len(result) >= 2

    def test_empty_xml_returns_empty(self, mocker):
        self._mock(mocker, EMPTY_XML)
        result = get_mrrf("2023-01-01", "2023-03-31")
        assert result.empty

    def test_uses_default_dates(self, mocker):
        self._mock(mocker)
        result = get_mrrf()
        assert isinstance(result, pd.DataFrame)

    def test_service_called_with_dates(self, mocker):
        mock_client = MagicMock()
        mock_client.service.mrrf.return_value = MRRF_XML
        mocker.patch("cbrapi.reserves.make_cbr_client", return_value=mock_client)
        get_mrrf("2023-01-01", "2023-03-31")
        assert mock_client.service.mrrf.called
