from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbr.cbr_settings import make_cbr_client
from cbr.helpers import normalize_data, guess_date

today = date.today()


def get_metals_prices(first_date: Optional[str] = None,
                     last_date: Optional[str] = None,
                     period: str = 'D') -> pd.Series:

    cbr_client = make_cbr_client()
    data1 = guess_date(first_date, default_value='1999-10-01')
    data2 = guess_date(last_date, default_value=str(today))
    metals_xml = cbr_client.service.DragMetDynamic(data1, data2)
    
    try:
        df = pd.read_xml(metals_xml, xpath=".//DrgMet")
    except ValueError:
        return pd.Series()    
    
    level_1_column_mapping = {
        1: 'GOLD',
        2: 'SILVER',
        3: 'PLATINUM',
        4: 'PALLADIUM', 
        }      
    
    df = normalize_data(data=df, period=period, symbol='DrgMet', level_1=level_1_column_mapping) 
    return df


