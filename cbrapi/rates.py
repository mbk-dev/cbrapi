from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbrapi.cbr_settings import make_cbr_client
from cbrapi.helpers import normalize_data, guess_date


today = date.today()


def get_key_rate(
    first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = "D"
) -> pd.Series:
    """
    Get the key rate time series from CBR.

    Parameters
    ----------
    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, defaults to
        '2013-09-13'.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, defaults to
        current date.

    period: {'D', 'M'}, default 'D'
        Data periodicity. Currently daily ('D') and monthly ('M') frequencies are supported.

    Returns
    -------
    pd.Series
        Time series of key rate values with datetime index.
        Rates are returned as decimals (e.g., 0.075 for 7.5%).

    Notes
    -----
    The key rate is the main instrument of the Bank of Russia's monetary policy.
    It influences interest rates in the economy and is used for liquidity provision
    and absorption operations.

    Examples
    --------
    >>> get_key_rate('2023-01-01', '2023-12-31')
    >>> get_key_rate(period='D')
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value="2013-09-13")
    data2 = guess_date(last_date, default_value=str(today))
    key_rate_xml = cbr_client.service.KeyRate(data1, data2)

    try:
        df = pd.read_xml(key_rate_xml, xpath=".//KR")
    except ValueError:
        return pd.Series()

    level_1_column_mapping = {"Rate": "KEY_RATE"}

    df = normalize_data(
        data=df, period=period, symbol="KEY_RATE", level_1=level_1_column_mapping
    )
    return df


def get_ibor(
    first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = "M"
) -> pd.DataFrame:
    """
    Get Interbank Offered Rate and related interbank rates from CBR.

    Parameters
    ----------
    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, defaults to
        '2013-09-13'.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, defaults to
        current date.

    period : {'M'}, default 'M'
        Data periodicity. Currently only monthly ('M') frequency is supported.

    Returns
    -------
    pd.DataFrame
        Multi-level DataFrame with datetime index containing interbank rates.
        First level columns represent tenors, second level represents rate types:

        Available loan terms:
        - D1 : 1 day
        - D7 : 7 days
        - D30 : 30 days
        - D180 : 180 days
        - D360 : 360 days

        Rate types include:
        - MIBID_RUB : Moscow Interbank Bid Rate (RUB)
        - MIBOR_RUB : Moscow Interbank Offered Rate (RUB)
        - MIACR_RUB : Moscow Interbank Actual Credit Rate (RUB)
        - MIACR_IG_RUB : MIACR for investment grade (RUB)
        - MIACR_RUB_TURNOVER : MIACR turnover (RUB)
        - MIACR_IG_RUB_TURNOVER : MIACR IG turnover (RUB)
        - MIACR_B_RUB : MIACR for banks (RUB)
        - MIACR_B_RUB_TURNOVER : MIACR banks turnover (RUB)
        - MIBID_USD : Moscow Interbank Bid Rate (USD)
        - MIBOR_USD : Moscow Interbank Offered Rate (USD)
        - MIACR_USD : Moscow Interbank Actual Credit Rate (USD)
        - MIACR_IG_USD : MIACR for investment grade (USD)
        - MIACR_USD_TURNOVER : MIACR turnover (USD)
        - MIACR_IG_USD_TURNOVER : MIACR IG turnover (USD)
        - MIACR_B_USD : MIACR for banks (USD)
        - MIACR_B_USD_TURNOVER : MIACR banks turnover (USD)

    Notes
    -----
    All rates are returned as decimals (e.g., 0.05 for 5%).
    Turnover values represent trading volumes.

    Examples
    --------
    >>> get_ibor('2023-01-01', '2023-12-31')
    >>> get_ibor(period='M')
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value="2013-09-13")
    data2 = guess_date(last_date, default_value=str(today))
    mkr_xml = cbr_client.service.MKR(data1, data2)

    try:
        df = pd.read_xml(mkr_xml, xpath=".//MKR")
    except ValueError:
        return pd.Series()

    level_0_column_mapping = {
        "d1": "D1",
        "d7": "D7",
        "d30": "D30",
        "d180": "D180",
        "d360": "D360",
    }

    level_1_column_mapping = {
        "1": "MIBID_RUB",
        "2": "MIBOR_RUB",
        "3": "MIACR_RUB",
        "4": "MIACR_IG_RUB",
        "5": "MIACR_RUB_TURNOVER",
        "6": "MIACR_IG_RUB_TURNOVER",
        "7": "MIACR_B_RUB",
        "8": "MIACR_B_RUB_TURNOVER",
        "9": "MIBID_USD",
        "10": "MIBOR_USD",
        "11": "MIACR_USD",
        "12": "MIACR_IG_USD",
        "13": "MIACR_USD_TURNOVER",
        "14": "MIACR_IG_USD_TURNOVER",
        "15": "MIACR_B_USD",
        "16": "MIACR_B_USD_TURNOVER",
    }

    df = normalize_data(
        data=df,
        period=period,
        symbol="MKR",
        level_0=level_0_column_mapping,
        level_1=level_1_column_mapping,
    )
    return df
