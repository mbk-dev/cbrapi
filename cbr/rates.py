from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbr.cbr_settings import make_cbr_client
from cbr.helpers import normalize_data, guess_date


today = date.today()


def get_key_rate(first_date: Optional[str] = None,
                 last_date: Optional[str] = None,
                 period: str = 'D') -> pd.Series:
    
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2013-09-13')
    data2 = guess_date(last_date, default_value=str(today))
    key_rate_xml = cbr_client.service.KeyRate(data1, data2)
    
    try:
        df = pd.read_xml(key_rate_xml, xpath=".//KR")
    except ValueError:
        return pd.Series()    

    level_1_column_mapping = {
        'Rate': 'KEY_RATE'
        }    
   
    df = normalize_data(data=df, period=period, symbol='KEY_RATE', level_1=level_1_column_mapping) 
    return df
    
    
def get_ibor(first_date: Optional[str] = None,
                 last_date: Optional[str] = None,
                 period: str = 'M') -> pd.Series:
    
    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='2013-09-13')
    data2 = guess_date(last_date, default_value=str(today))
    mkr_xml = cbr_client.service.MKR(data1, data2)

    try:
        df = pd.read_xml(mkr_xml, xpath=".//MKR")
    except ValueError:
        return pd.Series()    

    level_0_column_mapping = {
        'd1': 'D1',
        'd7': 'D7',
        'd30': 'D30', 
        'd180': 'D180',
        'd360': 'D360'             
        }

    level_1_column_mapping = {
        '1': 'MIBID_RUB',
        '2': 'MIBOR_RUB',
        '3': 'MIACR_RUB',
        '4': 'MIACR_IG_RUB', 
        '5': 'MIACR_RUB_TURNOVER',
        '6': 'MIACR_IG_RUB_TURNOVER',
        '7': 'MIACR_B_RUB',
        '8': 'MIACR_B_RUB_TURNOVER', 
        '9': 'MIBID_USD',
        '10': 'MIBOR_USD',
        '11': 'MIACR_USD',
        '12': 'MIACR_IG_USD', 
        '13': 'MIACR_USD_TURNOVER',
        '14': 'MIACR_IG_USD_TURNOVER',  
        '15': 'MIACR_B_USD',
        '16': 'MIACR_B_USD_TURNOVER'              
        }   
      
    
    df = normalize_data(data=df, period=period, symbol='MKR', level_0=level_0_column_mapping, level_1=level_1_column_mapping)  
    return df   
