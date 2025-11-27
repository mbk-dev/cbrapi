from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbrapi.cbr_settings import make_cbr_client
from cbrapi.helpers import normalize_data, guess_date


today = date.today()


def get_ruonia_ts(
    symbol: str,
    first_date: Optional[str] = None,
    last_date: Optional[str] = None,
    period: str = "D",
) -> pd.Series:
    """
    Get RUONIA (Ruble Overnight Index Average) time series data from CBR.

    Parameters
    ----------
    symbol : str
        Financial instrument symbol. Supported symbols:
        - 'RUONIA.INDX' : RUONIA index
        - 'RUONIA_AVG_1M.RATE' : 1-month average rate
        - 'RUONIA_AVG_3M.RATE' : 3-month average rate
        - 'RUONIA_AVG_6M.RATE' : 6-month average rate
        - Other symbols : return overnight RUONIA rates

    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, returns
        data from the earliest available date.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, returns
        data up to the most recent available date.

    period: {'D', 'M'}, default 'D'
        Data periodicity. Currently daily ('D') and monthly ('M') frequencies are supported.

    Returns
    -------
    pd.Series
        Time series data for the requested symbol with datetime index.
        Returns empty Series if no data is available for the given parameters.

    Notes
    -----
    Data is sourced from the Central Bank of Russia (CBR) official statistics.
    The function handles API requests and data parsing from CBR web services.

    Examples
    --------
    >>> get_ruonia_ts('RUONIA.INDX', '2023-01-01', '2023-12-31')
    >>> get_ruonia_ts('RUONIA_AVG_3M.RATE')
    """
    cbr_client = make_cbr_client()
    if symbol in [
        "RUONIA.INDX",
        "RUONIA_AVG_1M.RATE",
        "RUONIA_AVG_3M.RATE",
        "RUONIA_AVG_6M.RATE",
    ]:
        ticker = (
            symbol.split(".")[0] if symbol.split(".")[1] == "RATE" else "RUONIA_INDEX"
        )
        df = get_ruonia_index(first_date, last_date).loc[:, ticker]
        if symbol != "RUONIA.INDX":
            df /= 100
        return normalize_data(df, period, symbol)
    else:
        return get_ruonia_overnight(first_date, last_date, period)


def get_ruonia_index(
    first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = "D"
) -> pd.DataFrame:
    """
    Get RUONIA index and averages time series from CBR.

    Parameters
    ----------
    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, defaults to
        '2010-01-01'.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, defaults to
        current date.

    period: {'D', 'M'}, default 'D'
        Data periodicity. Currently daily ('D') and monthly ('M') frequencies are supported.

    Returns
    -------
    pd.DataFrame
        DataFrame with datetime index and the following columns:
        - RUONIA_INDEX : RUONIA index value
        - RUONIA_AVG_1M : 1-month average rate (as decimal)
        - RUONIA_AVG_3M : 3-month average rate (as decimal)
        - RUONIA_AVG_6M : 6-month average rate (as decimal)

    Notes
    -----
    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate
    on interbank loans and deposits. It serves as an indicator of the cost of
    unsecured overnight borrowing.

    Examples
    --------
    >>> get_ruonia_index('2023-01-01', '2023-12-31')
    >>> get_ruonia_index(period='D')
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value="2010-01-01")
    data2 = guess_date(last_date, default_value=str(today))
    ruonia_index_xml = cbr_client.service.RuoniaSV(data1, data2)

    try:
        df = pd.read_xml(ruonia_index_xml, xpath=".//ra")
    except ValueError:
        return pd.Series()

    level_1_column_mapping = {
        "RUONIA_Index": "RUONIA_INDEX",
        "R1W": "RUONIA_AVG_1M",
        "R2W": "RUONIA_AVG_3M",
        "R1M": "RUONIA_AVG_6M",
    }

    df = normalize_data(
        data=df, period=period, symbol="ra", level_1=level_1_column_mapping
    )
    return df


def get_ruonia_overnight(
    first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = "D"
) -> pd.Series:
    """
    Get RUONIA overnight value time series from CBR.

    Parameters
    ----------
    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, defaults to
        '2010-01-01'.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, defaults to
        current date.

    period: {'D', 'M'}, default 'D'
        Data periodicity. Currently daily ('D') and monthly ('M') frequencies are supported.

    Returns
    -------
    pd.Series
        Time series of RUONIA overnight rates with datetime index.
        Rates are returned as decimals (e.g., 0.05 for 5%).

    Notes
    -----
    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate
    on interbank loans and deposits. It serves as an indicator of the cost of
    unsecured overnight borrowing.

    Examples
    --------
    >>> get_ruonia_overnight('2023-01-01', '2023-12-31')
    >>> get_ruonia_overnight(period='D')
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value="2010-01-01")
    data2 = guess_date(last_date, default_value=str(date.today()))
    ruonia_overnight_xml = cbr_client.service.Ruonia(data1, data2)

    try:
        df = pd.read_xml(ruonia_overnight_xml, xpath="//ro")
    except ValueError:
        return pd.Series()

    level_1_column_mapping = {
        "ruo": "RUONIA_OVERNIGHT",
    }

    df = normalize_data(
        data=df, period=period, symbol="ro", level_1=level_1_column_mapping
    )
    df /= 100
    return df


def get_roisfix(
    first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = "D"
) -> pd.DataFrame:
    """
    Get ROISfix (Ruble Overnight Index Swap Fixing) time series from CBR.

    Parameters
    ----------
    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, defaults to
        '2011-04-15'.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, defaults to
        current date.

    period: {'D', 'M'}, default 'D'
        Data periodicity. Currently daily ('D') and monthly ('M') frequencies are supported.

    Returns
    -------
    pd.DataFrame
        DataFrame with datetime index and the following columns:
        - RATE_1_WEEK : 1-week ROISfix rate (as decimal)
        - RATE_2_WEEK : 2-week ROISfix rate (as decimal)
        - RATE_1_MONTH : 1-month ROISfix rate (as decimal)
        - RATE_2_MONTH : 2-month ROISfix rate (as decimal)
        - RATE_3_MONTH : 3-month ROISfix rate (as decimal)
        - RATE_6_MONTH : 6-month ROISfix rate (as decimal)

    Notes
    -----
    ROISfix represents the fixed rate in ruble overnight index swaps.

    Examples
    --------
    >>> get_roisfix('2023-01-01', '2023-12-31')
    >>> get_roisfix(period='D')
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value="2011-04-15")
    data2 = guess_date(last_date, default_value=str(today))
    roisfix_xml = cbr_client.service.ROISfix(data1, data2)

    try:
        df = pd.read_xml(roisfix_xml, xpath=".//rf")
    except ValueError:
        return pd.Series()

    level_1_column_mapping = {
        "R1W": "RATE_1_WEEK",
        "R2W": "RATE_2_WEEK",
        "R1M": "RATE_1_MONTH",
        "R2M": "RATE_2_MONTH",
        "R3M": "RATE_3_MONTH",
        "R6M": "RATE_6_MONTH",
    }

    df = normalize_data(
        data=df, period=period, symbol="rf", level_1=level_1_column_mapping
    )
    return df
