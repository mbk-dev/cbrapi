import re

import pandas as pd
from datetime import datetime

from cbr.cbr_settings import make_cbr_client
import cbr.helpers as helpers


def get_currencies_list() -> pd.DataFrame:
    """
    Get a list of available currencies from CBR.RU.
    """
    cbr_client = make_cbr_client()
    # get currency table with DAILY time series
    currencies_daily_xml = cbr_client.service.EnumValutesXML(False)
    df_daily = pd.read_xml(currencies_daily_xml, xpath="//EnumValutes")

    # get currency table with MONTHLY time series
    currencies_monthly_xml = cbr_client.service.EnumValutesXML(True)
    df_monthly = pd.read_xml(currencies_monthly_xml, xpath="//EnumValutes")
    return pd.concat([df_daily, df_monthly], axis=0, join="outer", copy="false")


def get_currency_code(ticker: str) -> str:
    """
    Return an internal CBR currency code for a ticker:
    USDRUB.CBR -> R01235
    """
    cbr_symbol = ticker[:3]
    currencies_list = get_currencies_list()
    # Some tickers has 2 Vcode in CBR database. ILS - "Израильский шекель" and "Новый израильский шекель"
    # First row is taken with .iloc
    row = currencies_list[currencies_list['VcharCode'] == cbr_symbol].iloc[0, :].squeeze()
    try:
        code = row.loc['Vcode']
    except KeyError as e:
        raise ValueError(f"There is no {ticker} in CBR database.") from e
    return code


def get_time_series(symbol: str, first_date: str, last_date: str, period: str = 'D') -> pd.Series:
    """
    Get currency rate historical data from CBR.RU.

    Some tickers (EEKRUB.CBR) return empy data.

    Input Columns:
    'rowOrder', 'Vcode', 'VunitRate', 'Vnom', 'CursDate', 'Vcurs', 'id'
    or
    'rowOrder', 'id', 'Vnom', 'Vcode', 'CursDate', 'Vcurs'
    """
    try:
        data1 = datetime.strptime(first_date, "%Y-%m-%d")
        data2 = datetime.strptime(last_date, "%Y-%m-%d")
    except ValueError:
        data1 = datetime.strptime(first_date, "%Y-%m")
        data2 = datetime.strptime(last_date, "%Y-%m")
    symbol = symbol.upper()
    if re.match("RUB", symbol):
        foreign_ccy = re.search(r'^RUB(.*).CBR$', symbol)[1]
        query_symbol = foreign_ccy + "RUB.CBR"
        method = "inverse"
    else:
        query_symbol = symbol
        method = "direct"
    code = get_currency_code(query_symbol)
    cbr_client = make_cbr_client()
    rate_xml = cbr_client.service.GetCursDynamic(data1, data2, code)
    try:
        df = pd.read_xml(rate_xml, xpath="//ValuteCursDynamic")
    except ValueError:
        return pd.Series()
    cbr_cols1 = {'rowOrder', 'id', 'Vnom', 'Vcode', 'CursDate', 'Vcurs'}
    cbr_cols2 = cbr_cols1.union({'VunitRate'})
    if set(df.columns) not in [cbr_cols1, cbr_cols2]:
        raise ValueError("CBR data has different columns. Probably data format is changed.")
    df.drop(columns=['id', 'rowOrder', 'Vcode'], inplace=True)
    if 'VunitRate' in list(df.columns):
        df.drop(columns=['VunitRate'], inplace=True)
    df['Vcurs'] /= df['Vnom']
    df.drop(columns=['Vnom'], inplace=True)
    df = df.astype({'CursDate': 'period[D]'}, copy=False)
    df = df.astype({'Vcurs': 'float'}, copy=False)
    df.set_index('CursDate', inplace=True, verify_integrity=True)
    df.sort_index(ascending=True, inplace=True)
    s = df.squeeze(axis=1)  # all outputs must be pd.Series
    s = helpers.pad_missing_periods(s, freq='D')
    s.index.rename('date', inplace=True)
    if period.upper() == 'M':
        s = s.resample('M').last()
    s = helpers.calculate_inverse_rate(s) if method == "inverse" else s
    return s.rename(symbol)
