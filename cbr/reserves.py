from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbr.cbr_settings import make_cbr_client
from cbr.helpers import normalize_data, guess_date

today = date.today()


def get_mrrf(first_date: Optional[str] = None,
                     last_date: Optional[str] = None,
                     period: str = 'M') -> pd.Series:
    
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
