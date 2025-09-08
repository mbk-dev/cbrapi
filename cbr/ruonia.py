from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbr.cbr_settings import make_cbr_client
from cbr.helpers import normalize_data, guess_date


today = date.today()


def get_ruonia_ts(symbol: str,
                  first_date: Optional[str] = None,
                  last_date: Optional[str] = None,
                  period: str = 'D') -> pd.Series:
    """
    Get RUONIA (Ruble Overnight Index Swap Fixing) time series data for the specified symbol from the Central Bank of Russia.
    
    Supported symbols:
    - RUONIA.INDX - RUONIA index
    - RUONIA_AVG_1M.RATE - 1-month average rate
    - RUONIA_AVG_3M.RATE - 3-month average rate  
    - RUONIA_AVG_6M.RATE - 6-month average rate
    - Other symbols will return overnight RUONIA rates
    
    Args:
        symbol: Financial instrument symbol
        first_date: Start date in format 'YYYY-MM-DD' (optional)
        last_date: End date in format 'YYYY-MM-DD' (optional)
        period: Data periodicity ('D' for daily, etc.)
    
    Returns:
        pd.Series: Time series data for the requested symbol
    """
    cbr_client = make_cbr_client()
    if symbol in ['RUONIA.INDX',  'RUONIA_AVG_1M.RATE', 'RUONIA_AVG_3M.RATE',  'RUONIA_AVG_6M.RATE']:
        ticker = symbol.split('.')[0] if symbol.split('.')[1] == 'RATE' else 'RUONIA_INDEX'
        df = get_ruonia_index(first_date, last_date).loc[:, ticker]
        if symbol != 'RUONIA.INDX':
            df /= 100
        return normalize_data(df, period, symbol)
    else:
        return get_ruonia_overnight(first_date, last_date, period)


def get_ruonia_index(first_date: Optional[str] = None,
                     last_date: Optional[str] = None,
                     period: str = 'D') -> pd.DataFrame:
    """
    Get RUONIA (Ruble Overnight Index Swap Fixing) index and averages time series from the Central Bank of Russia.

    Returns a DataFrame with columns:
    - RUONIA_INDEX: RUONIA index value
    - RUONIA_AVG_1M: 1-month average rate
    - RUONIA_AVG_3M: 3-month average rate  
    - RUONIA_AVG_6M: 6-month average rate

    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate 
    on interbank loans and deposits. It serves as an indicator of the cost of 
    unsecured overnight borrowing.
    
    Args:
        first_date: Start date in format 'YYYY-MM-DD' (optional)
        last_date: End date in format 'YYYY-MM-DD' (optional)
        period: Data periodicity ('D' for daily, etc.)
    
    Returns:
        pd.DataFrame: Time series data with RUONIA index and averages
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2010-01-01')
    data2 = guess_date(last_date, default_value=str(today))
    ruonia_index_xml = cbr_client.service.RuoniaSV(data1, data2)
    
    try:
        df = pd.read_xml(ruonia_index_xml, xpath=".//ra")
    except ValueError:
        return pd.Series()
        
    level_1_column_mapping = {
        'RUONIA_Index': 'RUONIA_INDEX',
        'R1W': 'RUONIA_AVG_1M',
        'R2W': 'RUONIA_AVG_3M',
        'R1M': 'RUONIA_AVG_6M'
        }  
                                   
    df = normalize_data(data=df, period=period, symbol='ra', level_1=level_1_column_mapping)     
    return df 


def get_ruonia_overnight(first_date: Optional[str] = None,
                         last_date: Optional[str] = None,
                         period: str = 'D') -> pd.Series:
    """
    Get RUONIA (Ruble Overnight Index Swap Fixing) overnight value time series from the Central Bank of Russia.

    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate 
    on interbank loans and deposits. It serves as an indicator of the cost of 
    unsecured overnight borrowing.
    
    Args:
        first_date: Start date in format 'YYYY-MM-DD' (optional)
        last_date: End date in format 'YYYY-MM-DD' (optional)
        period: Data periodicity ('D' for daily, etc.)
    
    Returns:
        pd.Series: Time series of RUONIA overnight rates (as decimals, e.g., 0.05 for 5%)
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2010-01-01')
    data2 = guess_date(last_date, default_value=str(date.today()))
    ruonia_overnight_xml = cbr_client.service.Ruonia(data1, data2)
    
    try:
        df = pd.read_xml(ruonia_overnight_xml, xpath="//ro")
    except ValueError:
        return pd.Series()

    level_1_column_mapping = {
        'ruo': 'RUONIA_OVERNIGHT',
        } 
        
    df = normalize_data(data=df, period=period, symbol='ro', level_1=level_1_column_mapping)  
    df /= 100
    return df
    
    
def get_roisfix(first_date: Optional[str] = None,
                last_date: Optional[str] = None,
                 period: str = 'D') -> pd.DataFrame:       
    """
    Get ROISfix (Ruble Overnight Index Swap Fixing) time series data from the Central Bank of Russia.
    
    Returns a DataFrame with various term rates:
    - RATE_1_WEEK: 1-week rate
    - RATE_2_WEEK: 2-week rate  
    - RATE_1_MONTH: 1-month rate
    - RATE_2_MONTH: 2-month rate
    - RATE_3_MONTH: 3-month rate
    - RATE_6_MONTH: 6-month rate
    
    ROISfix represents the fixed rate in ruble overnight index swaps.
    
    Args:
        first_date: Start date in format 'YYYY-MM-DD' (optional)
        last_date: End date in format 'YYYY-MM-DD' (optional)
        period: Data periodicity ('D' for daily, etc.)
    
    Returns:
        pd.DataFrame: Time series data with ROISfix rates for different terms
    """                     
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2011-04-15')   
    data2 = guess_date(last_date, default_value=str(today))
    roisfix_xml = cbr_client.service.ROISfix(data1, data2)
    
    try:
        df = pd.read_xml(roisfix_xml, xpath=".//rf")
    except ValueError:
        return pd.Series()
        
    level_1_column_mapping = {
        'R1W': 'RATE_1_WEEK',
        'R2W': 'RATE_2_WEEK',
        'R1M': 'RATE_1_MONTH',
        'R2M': 'RATE_2_MONTH', 
        'R3M': 'RATE_3_MONTH',   
        'R6M': 'RATE_6_MONTH'
        }  
                                   
    df = normalize_data(data=df, period=period, symbol='rf', level_1=level_1_column_mapping)     
    return df
