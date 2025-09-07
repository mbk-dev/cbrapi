from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbr.cbr_settings import make_cbr_client
from cbr.helpers import normalize_data, guess_date


today = date.today()


def get_mrrf(first_date: Optional[str] = None,
                     last_date: Optional[str] = None,
                     period: str = 'M') -> pd.DataFrame:
    """
    Get International Reserves and Foreign Currency Liquidity data from the Central Bank of Russia.
    
    Returns a DataFrame with monthly data on Russia's international reserves components:
    - TOTAL_RESERVES: Total international reserves
    - CURRENCY_RESERVES: Currency reserves
    - FOREIGN_CURRENCY: Foreign currency holdings
    - SDR_ACCOUNT: Special Drawing Rights (SDR) account
    - IMF_RESERVE: Reserve position in International Monetary Fund (IMF)
    - MONETARY_GOLD: Monetary gold holdings
    
    International reserves are external assets that are readily available to and controlled by 
    monetary authorities for meeting balance of payments financing needs, for intervention in 
    exchange markets to affect the currency exchange rate, and for other related purposes.
    
    Args:
        first_date: Start date in format 'YYYY-MM-DD' (optional, defaults to '1999-01-01')
        last_date: End date in format 'YYYY-MM-DD' (optional, defaults to current date)
        period: Data periodicity ('M' for monthly, etc.)
    
    Returns:
        pd.DataFrame: Time series of international reserves components in USD
    """    
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='1999-01-01')
    data2 = guess_date(last_date, default_value=str(today))    
    mrrf_xml = cbr_client.service.mrrf(data1, data2)
    
    try:
        df = pd.read_xml(mrrf_xml, xpath=".//mr")
    except ValueError:
        return pd.Series()    
    
    level_1_column_mapping = {
        'p1': 'TOTAL_RESERVES',
        'p2': 'CURRENCY_RESERVES',
        'p3': 'FOREIGN_CURRENCY',
        'p4': 'SDR_ACCOUNT', 
        'p5': 'IMF_RESERVE',
        'p6': 'MONETARY_GOLD'
        }
        
    df = normalize_data(data=df, period=period, symbol='mr', level_1=level_1_column_mapping)  

    return df
