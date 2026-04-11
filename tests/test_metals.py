import pytest
import pandas as pd
from unittest.mock import MagicMock

from cbrapi.metals import get_metals_prices

# One row per (date, metal). CodMet: 1=GOLD 2=SILVER 3=PLATINUM 4=PALLADIUM
METALS_XML = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <DrgMet>
    <DateMet>2023-01-03T00:00:00</DateMet>
    <CodMet>1</CodMet>
    <price>3750.25</price>
    <id>1</id>
    <rowOrder>0</rowOrder>
    <vol>0</vol>
  </DrgMet>
  <DrgMet>
    <DateMet>2023-01-03T00:00:00</DateMet>
    <CodMet>2</CodMet>
    <price>46.80</price>
    <id>2</id>
    <rowOrder>1</rowOrder>
    <vol>0</vol>
  </DrgMet>
  <DrgMet>
    <DateMet>2023-01-03T00:00:00</DateMet>
    <CodMet>3</CodMet>
    <price>2105.60</price>
    <id>3</id>
    <rowOrder>2</rowOrder>
    <vol>0</vol>
  </DrgMet>
  <DrgMet>
    <DateMet>2023-01-03T00:00:00</DateMet>
    <CodMet>4</CodMet>
    <price>1820.40</price>
    <id>4</id>
    <rowOrder>3</rowOrder>
    <vol>0</vol>
  </DrgMet>
  <DrgMet>
    <DateMet>2023-01-10T00:00:00</DateMet>
    <CodMet>1</CodMet>
    <price>3800.00</price>
    <id>5</id>
    <rowOrder>4</rowOrder>
    <vol>0</vol>
  </DrgMet>
  <DrgMet>
    <DateMet>2023-01-10T00:00:00</DateMet>
    <CodMet>2</CodMet>
    <price>47.20</price>
    <id>6</id>
    <rowOrder>5</rowOrder>
    <vol>0</vol>
  </DrgMet>
  <DrgMet>
    <DateMet>2023-01-10T00:00:00</DateMet>
    <CodMet>3</CodMet>
    <price>2120.00</price>
    <id>7</id>
    <rowOrder>6</rowOrder>
    <vol>0</vol>
  </DrgMet>
  <DrgMet>
    <DateMet>2023-01-10T00:00:00</DateMet>
    <CodMet>4</CodMet>
    <price>1840.00</price>
    <id>8</id>
    <rowOrder>7</rowOrder>
    <vol>0</vol>
  </DrgMet>
</root>"""

EMPTY_XML = "<?xml version='1.0'?><root/>"


def _make_mock_client(xml=METALS_XML):
    mock_client = MagicMock()
    mock_client.service.DragMetDynamic.return_value = xml
    return mock_client


class TestGetMetalsPrices:
    def test_returns_dataframe(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices("2023-01-01", "2023-01-15")
        assert isinstance(result, pd.DataFrame)

    def test_has_all_metal_columns(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices("2023-01-01", "2023-01-15")
        assert set(result.columns) == {"GOLD", "SILVER", "PLATINUM", "PALLADIUM"}

    def test_values_are_numeric(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices("2023-01-01", "2023-01-15")
        assert result["GOLD"].dtype == float

    def test_gold_value_correct(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices("2023-01-01", "2023-01-15")
        assert result["GOLD"].iloc[0] == pytest.approx(3750.25)

    def test_has_period_index(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices("2023-01-01", "2023-01-15")
        assert isinstance(result.index, pd.PeriodIndex)

    def test_gaps_padded_by_forward_fill(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices("2023-01-01", "2023-01-15")
        # 2023-01-03 to 2023-01-10 = 8 rows after forward fill
        assert len(result) >= 8

    def test_uses_default_dates_when_none_given(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices()
        assert isinstance(result, pd.DataFrame)

    def test_monthly_period_resamples(self, mocker):
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=_make_mock_client())
        result = get_metals_prices("2023-01-01", "2023-01-31", period="M")
        assert isinstance(result, pd.DataFrame)
        assert set(result.columns) == {"GOLD", "SILVER", "PLATINUM", "PALLADIUM"}

    def test_empty_xml_returns_empty(self, mocker):
        mock_client = MagicMock()
        mock_client.service.DragMetDynamic.return_value = EMPTY_XML
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=mock_client)
        result = get_metals_prices("2023-01-01", "2023-01-15")
        assert result.empty

    def test_service_called_with_dates(self, mocker):
        mock_client = _make_mock_client()
        mocker.patch("cbrapi.metals.make_cbr_client", return_value=mock_client)
        get_metals_prices("2023-01-01", "2023-01-15")
        assert mock_client.service.DragMetDynamic.called
