import re
from datetime import datetime, date
from functools import lru_cache
from io import BytesIO

import pandas as pd

from cbrapi.cbr_settings import make_cbr_client
from cbrapi.helpers import (
    pad_missing_periods,
    calculate_inverse_rate,
    check_ticker_code,
    check_symbol_ts,
)

today = date.today()


@lru_cache(maxsize=1)
def get_currencies_list() -> pd.DataFrame:
    """
    Get a list of available currencies from CBR.

    Returns
    -------
    pd.DataFrame
        Combined dataframe with all available currencies for daily and monthly frequencies.
        Contains currency codes, character codes, names, and metadata.

    Notes
    -----
    The function retrieves two separate lists:
    - Currencies with DAILY time series data
    - Currencies with MONTHLY time series data
    Returns a combined dataframe with all available currencies.

    Examples
    --------
    >>> get_currencies_list()
    """
    cbr_client = make_cbr_client()
    # get currency table with DAILY time series
    currencies_daily_xml = cbr_client.service.EnumValutesXML(False)
    df_daily = pd.read_xml(BytesIO(currencies_daily_xml), xpath="//EnumValutes")

    # get currency table with MONTHLY time series
    currencies_monthly_xml = cbr_client.service.EnumValutesXML(True)
    df_monthly = pd.read_xml(BytesIO(currencies_monthly_xml), xpath="//EnumValutes")
    return pd.concat([df_daily, df_monthly], axis=0, join="outer")


def get_currency_code(ticker: str) -> str:
    """
    Return an internal CBR currency code for a ticker.

    Parameters
    ----------
    ticker : str
        Currency ticker in format 'CCY' (e.g., 'USD')

    Returns
    -------
    str
        Internal CBR currency code (e.g., 'R01235')

    Raises
    ------
    ValueError
        If the currency ticker is not found in the CBR database.

    Notes
    -----
    Handles cases where multiple currency codes might exist for the same ticker
    by selecting the first available option.

    Examples
    --------
    >>> get_currency_code('USD')
    'R01235'
    """
    currencies_list = get_currencies_list()
    symbol_col = currencies_list["VcharCode"]
    ticker = check_ticker_code(ticker, symbol_col)

    # Some tickers has 2 Vcode in CBR database. ILS - "Израильский шекель" and "Новый израильский шекель"
    # First row is taken with .iloc
    row = currencies_list[currencies_list["VcharCode"] == ticker].iloc[0, :].squeeze()
    try:
        code = row.loc["Vcode"]
    except KeyError as e:
        raise ValueError(f"There is no {ticker} in CBR database.") from e
    return code


def _collapse_duplicate_code_dates(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """Keep one row per date when CBR lists a date under more than one code.

    GetCursDynamic answers with a currency's *continuous* history, so rows of
    other codes are normal and carry real data (most of the Romanian Leu series
    comes back under R01585F, not the requested R01585). They must not be
    filtered out.

    On the Bulgarian Lev redenomination CBR lists 1999-07-01 twice: R01100 at
    Vnom=1000 (12.89, the requested code's own quote) and R01100Z at Vnom=1
    (12.77). R01100Z occurs exactly once in 4152 rows and the series continues
    under R01100 from 1999-08-01, so it is a one-off annotation of the event
    rather than a successor. The tie therefore goes to the row of the requested
    code, which keeps the unit break where CBR's own regular series puts it.

    Vcode is a space-padded fixed-width field on both sides, so both are
    stripped before comparing, and the choice is made by code rather than by the
    order rows happen to arrive in: picking the other row is a silent 1000x
    error, not a failure.

    When the duplicated date carries no row of the requested code there is
    nothing to prefer, so the row that closes the day by rowOrder is kept. A
    date repeated under the *requested* code is left alone: that is a genuine
    anomaly and must keep tripping the uniqueness check downstream.
    """
    duplicated = df["CursDate"].duplicated(keep=False)
    if not duplicated.any():
        return df
    codes = df["Vcode"].astype(str).str.strip()
    codes_per_date = codes[duplicated].groupby(df.loc[duplicated, "CursDate"]).nunique()
    ambiguous_dates = codes_per_date[codes_per_date > 1].index
    if ambiguous_dates.empty:
        return df

    requested = str(code).strip()
    superseded: list = []
    for curs_date in ambiguous_dates:
        rows = list(df.index[df["CursDate"] == curs_date])
        own = [index for index in rows if codes[index] == requested]
        if len(own) > 1:
            continue
        if own:
            keep = own[0]
        else:
            keep = df.loc[rows].sort_values("rowOrder", kind="stable").index[-1]
        superseded.extend(index for index in rows if index != keep)
    if not superseded:
        return df
    return df.drop(index=superseded).copy()


def get_time_series(symbol: str, first_date: str, last_date: str, period: str = "D") -> pd.Series:
    """
    Get currency rate historical data from CBR.

    Parameters
    ----------
    symbol : str
        Currency pair symbol in format 'CCY' (e.g., 'USD')

    first_date : str
        Start date in format 'YYYY-MM-DD' or 'YYYY-MM'

    last_date : str
        End date in format 'YYYY-MM-DD' or 'YYYY-MM'

    period: {'D', 'M'}, default 'D'
        Data periodicity. Currently daily ('D') and monthly ('M') frequencies are supported.

    Returns
    -------
    pd.Series
        Time series of currency exchange rates with datetime index.

    Raises
    ------
    ValueError
        If the CBR data format has changed unexpectedly.
        If date format is invalid.
        If currency symbol is not found.

    Notes
    -----
    - Supports both direct and inverse rate calculations
    - Handles data normalization and missing period padding
    - Performs resampling for different frequencies
    - Some tickers may return empty data if not available

    Examples
    --------
    >>> get_time_series('USD', '2023-01-01', '2023-12-31', 'D')
    >>> get_time_series('EUR', '2023-01', '2023-12', 'M')
    """
    try:
        data1 = datetime.strptime(first_date, "%Y-%m-%d")
        data2 = datetime.strptime(last_date, "%Y-%m-%d")
    except ValueError:
        data1 = datetime.strptime(first_date, "%Y-%m")
        data2 = datetime.strptime(last_date, "%Y-%m")
    symbol = symbol.upper()

    if re.match("RUB", symbol):
        foreign_ccy = re.search(r"^RUB(.*)$", symbol)[1]
        query_symbol = foreign_ccy
        method = "inverse"
    else:
        query_symbol = symbol
        method = "direct"

    symbol_col = get_currencies_list()["VcharCode"]
    check_symbol_ts(symbol, symbol_col)

    code = get_currency_code(query_symbol)
    cbr_client = make_cbr_client()
    rate_xml = cbr_client.service.GetCursDynamic(data1, data2, code)
    try:
        df = pd.read_xml(BytesIO(rate_xml), xpath="//ValuteCursDynamic")
    except ValueError:
        return pd.Series(dtype=float)
    cbr_cols1 = {"rowOrder", "id", "Vnom", "Vcode", "CursDate", "Vcurs"}
    cbr_cols2 = cbr_cols1.union({"VunitRate"})
    if set(df.columns) not in [cbr_cols1, cbr_cols2]:
        raise ValueError("CBR data has different columns. Probably data format is changed.")
    df = _collapse_duplicate_code_dates(df, code)
    df.drop(columns=["id", "rowOrder", "Vcode"], inplace=True)
    if "VunitRate" in list(df.columns):
        df.drop(columns=["VunitRate"], inplace=True)
    df["Vcurs"] /= df["Vnom"]
    df.drop(columns=["Vnom"], inplace=True)
    df = df.astype({"CursDate": "period[D]"})
    df = df.astype({"Vcurs": "float"})
    df.set_index("CursDate", inplace=True)
    if not df.index.is_unique:
        raise ValueError("CBR returned duplicate dates. Probably data format is changed.")
    df.sort_index(ascending=True, inplace=True)
    s = df.squeeze(axis=1)  # all outputs must be pd.Series
    pad_end_date = data2.date()
    if data1.date() < today < data2.date():
        pad_end_date = today
    s = pad_missing_periods(s, freq="D", end_date=pad_end_date)
    s.index.rename("date", inplace=True)
    if period.upper() == "M":
        s = s.to_timestamp().resample("ME").last()
    s = calculate_inverse_rate(s) if method == "inverse" else s
    return s.rename(symbol)
