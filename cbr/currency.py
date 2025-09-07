import re
from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbr.cbr_settings import make_cbr_client
from cbr.helpers import normalize_data, guess_date, pad_missing_periods, calculate_inverse_rate


today = date.today()


def get_currencies_list() -> pd.DataFrame:
    """
    Get a list of available currencies from the Central Bank of Russia.
    
    Returns a comprehensive list of currencies available from the Central Bank of Russia
    with both daily and monthly time series data. The list includes currency codes,
    character codes, names, and other metadata.
    
    Returns:
        pd.DataFrame: Combined dataframe with all available currencies for daily and monthly frequencies
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
    Return an internal CBR currency code for a ticker.
    
    Converts a currency ticker (e.g., 'USDRUB.CBR') to the internal CBR currency code
    (e.g., 'R01235'). Handles cases where multiple currency codes might exist for the
    same ticker by selecting the first available option.
    
    Args:
        ticker: Currency ticker in format 'CCY1CCY2.CBR' (e.g., 'USDRUB.CBR')
    
    Returns:
        str: Internal CBR currency code
        
    Raises:
        ValueError: If the currency ticker is not found in the CBR database
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
    Get currency rate historical data from the Central Bank of Russia.
    
    Retrieves historical exchange rate data for the specified currency pair and date range.
    Supports both direct and inverse rate calculations. Handles data normalization, missing
    period padding, and resampling for different frequencies.
    
    Note: Some tickers (like EEKRUB.CBR) may return empty data if not available.
    
    Args:
        symbol: Currency pair symbol in format 'CCY1CCY2.CBR' (e.g., 'USDRUB.CBR')
        first_date: Start date in format 'YYYY-MM-DD' or 'YYYY-MM'
        last_date: End date in format 'YYYY-MM-DD' or 'YYYY-MM'
        period: Data frequency ('D' for daily, 'M' for monthly)
    
    Returns:
        pd.Series: Time series of currency exchange rates
        
    Raises:
        ValueError: If the CBR data format has changed unexpectedly
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
    s = pad_missing_periods(s, freq='D')
    s.index.rename('date', inplace=True)
    if period.upper() == 'M':
        s = s.resample('M').last()
    s = calculate_inverse_rate(s) if method == "inverse" else s
    return s.rename(symbol)
