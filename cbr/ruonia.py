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
    cbr_client = make_cbr_client()
    if symbol in ['RUONIA.INDX',  'RUONIA_AVG_1M.RATE', 'RUONIA_AVG_3M.RATE',  'RUONIA_AVG_6M.RATE']:
        ticker = symbol.split('.')[0] if symbol.split('.')[1] == 'RATE' else 'RUONIA_INDEX'
        df = get_ruonia_index(cbr_client, first_date, last_date).loc[:, ticker]
        if symbol != 'RUONIA.INDX':
            df /= 100
        return normalize_data(df, period, symbol)
    else:
        return get_ruonia_overnight(cbr_client, first_date, last_date, period)


def get_ruonia_index(first_date: Optional[str] = None,
                     last_date: Optional[str] = None) -> pd.DataFrame:
    """
    Get RUONIA index and averages time series.

    Averages: 'RUONIA_AVG_1M', 'RUONIA_AVG_3M', 'RUONIA_AVG_6M'

    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate on interbank loans and deposits.
    It serves as an indicator of the cost of unsecured overnight borrowing.
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2010-01-01')
    data2 = guess_date(last_date, default_value=str(date.today()))
    ruonia_xml = cbr_client.service.RuoniaSV(data1, data2)
    try:
        df = pd.read_xml(ruonia_xml, xpath="//ra")
    except ValueError:
        return pd.Series()
    df.drop(columns=['id', 'rowOrder'], inplace=True)
    df = df.astype({'DT': 'period[D]'}, copy=False)
    df.columns = [s.upper() for s in df.columns]
    float_columns = ['RUONIA_INDEX', 'RUONIA_AVG_1M', 'RUONIA_AVG_3M', 'RUONIA_AVG_6M']
    df[float_columns] = df[float_columns].astype('float', copy=False)
    df.set_index('DT', inplace=True, verify_integrity=True)
    df.sort_index(ascending=True, inplace=True)
    df.index.rename('date', inplace=True)
    return df


def get_ruonia_overnight(first_date: Optional[str] = None,
                         last_date: Optional[str] = None,
                         period: str = 'D') -> pd.Series:
    """
    Get RUONIA overnight value time series.

    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate on interbank loans and deposits.
    It serves as an indicator of the cost of unsecured overnight borrowing.
    """
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2010-01-01')
    data2 = guess_date(last_date, default_value=str(date.today()))
    ruonia_xml = cbr_client.service.Ruonia(data1, data2)
    try:
        df = pd.read_xml(ruonia_xml, xpath="//ro")
    except ValueError:
        return pd.Series()
    df.drop(columns=['id', 'rowOrder', 'vol', 'DateUpdate'], inplace=True)
    df = df.astype({'D0': 'period[D]'}, copy=False)
    float_columns = ['ruo']
    df[float_columns] = df[float_columns].astype('float', copy=False)
    df.set_index('D0', inplace=True, verify_integrity=True)
    df.sort_index(ascending=True, inplace=True)
    df /= 100
    return normalize_data(df, period, 'RUONIA.RATE')
    
    
def get_ruoniasv(first_date: Optional[str] = None,
                last_date: Optional[str] = None,
                 period: str = 'D') -> pd.Series:    
                  
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2010-04-15')   
    data2 = guess_date(last_date, default_value=str(today))
    ruoniasv_xml = cbr_client.service.RuoniaSV(data1, data2)
    
    try:
        df = pd.read_xml(ruoniasv_xml, xpath=".//ra")
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
    
    
def get_roisfix(first_date: Optional[str] = None,
                last_date: Optional[str] = None,
                 period: str = 'D') -> pd.Series:       
                  
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
        'R1M': 'RATE_2_MONTH', 
        'R2M': 'RATE_3_MONTH',   
        'R6M': 'RATE_6_MONTH'
        }  
                                   
    df = normalize_data(data=df, period=period, symbol='rf', level_1=level_1_column_mapping)     
    return df
