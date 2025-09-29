from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbrapi.cbr_settings import make_cbr_client
from cbrapi.helpers import normalize_data, guess_date


today = date.today()


def get_metals_prices(
    first_date: Optional[str] = None, last_date: Optional[str] = None, period: str = "D"
) -> pd.DataFrame:
    """
    Get precious metals prices time series from CBR.

    Parameters
    ----------
    first_date : str, optional
        Start date in format 'YYYY-MM-DD'. If not specified, defaults to
        '1999-10-01'.

    last_date : str, optional
        End date in format 'YYYY-MM-DD'. If not specified, defaults to
        current date.

    period: {'D', 'M'}, default 'D'
        Data periodicity. Currently daily ('D') and monthly ('M') frequencies are supported.

    Returns
    -------
    pd.DataFrame
        DataFrame with datetime index and the following columns:
        - GOLD : Gold price (RUB per gram)
        - SILVER : Silver price (RUB per gram)
        - PLATINUM : Platinum price (RUB per gram)
        - PALLADIUM : Palladium price (RUB per gram)

    Notes
    -----
    Prices are provided in Russian Rubles per gram.
    Data is available from October 1999.

    Examples
    --------
    >>> get_metals_prices('2023-01-01', '2023-12-31')
    >>> get_metals_prices(period='M')
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value="1999-10-01")
    data2 = guess_date(last_date, default_value=str(today))
    metals_xml = cbr_client.service.DragMetDynamic(data1, data2)

    try:
        df = pd.read_xml(metals_xml, xpath=".//DrgMet")
    except ValueError:
        return pd.Series()

    level_1_column_mapping = {
        1: "GOLD",
        2: "SILVER",
        3: "PLATINUM",
        4: "PALLADIUM",
    }

    df = normalize_data(
        data=df, period=period, symbol="DrgMet", level_1=level_1_column_mapping
    )
    return df
