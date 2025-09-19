from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbrapi.cbr_settings import make_cbr_client
from cbrapi.helpers import normalize_data, guess_date


today = date.today()


def get_mrrf(
    first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = "M"
) -> pd.DataFrame:
    """
    Get International Reserves and Foreign Currency Liquidity data from CBR.

    Parameters
    ----------
    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, defaults to
        '1999-01-01'.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, defaults to
        current date.

    period : {'M'}, default 'M'
        Data periodicity. Currently only monthly ('M') frequency is supported.

    Returns
    -------
    pd.DataFrame
        DataFrame with datetime index and the following columns:
        - TOTAL_RESERVES : Total international reserves (USD)
        - CURRENCY_RESERVES : Currency reserves (USD)
        - FOREIGN_CURRENCY : Foreign currency holdings (USD)
        - SDR_ACCOUNT : Special Drawing Rights (SDR) account (USD)
        - IMF_RESERVE : Reserve position in IMF (USD)
        - MONETARY_GOLD : Monetary gold holdings (USD)

    Notes
    -----
    International reserves are external assets that are readily available to and
    controlled by monetary authorities for:
    - Meeting balance of payments financing needs
    - Intervention in exchange markets to affect currency exchange rate
    - Other related purposes

    All values are reported in US dollars.

    Examples
    --------
    >>> get_mrrf('2020-01-01', '2023-12-31')
    >>> get_mrrf(period='M')
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value="1999-01-01")
    data2 = guess_date(last_date, default_value=str(today))
    mrrf_xml = cbr_client.service.mrrf(data1, data2)

    try:
        df = pd.read_xml(mrrf_xml, xpath=".//mr")
    except ValueError:
        return pd.Series()

    level_1_column_mapping = {
        "p1": "TOTAL_RESERVES",
        "p2": "CURRENCY_RESERVES",
        "p3": "FOREIGN_CURRENCY",
        "p4": "SDR_ACCOUNT",
        "p5": "IMF_RESERVE",
        "p6": "MONETARY_GOLD",
    }

    df = normalize_data(
        data=df, period=period, symbol="mr", level_1=level_1_column_mapping
    )

    return df
