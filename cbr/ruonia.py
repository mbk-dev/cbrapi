from datetime import datetime, date
from typing import Optional

import pandas as pd

from cbr.cbr_settings import make_cbr_client
from cbr.helpers import pad_missing_periods


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
        return squeeze_df(df, period, symbol)
    else:
        return get_ruonia_overnight(cbr_client, first_date, last_date, period)


def get_ruonia_index(cbr_client,
                     first_date: Optional[str] = None,
                     last_date: Optional[str] = None) -> pd.DataFrame:
    """
    Get RUONIA index and averages time series.

    Averages: 'RUONIA_AVG_1M', 'RUONIA_AVG_3M', 'RUONIA_AVG_6M'

    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate on interbank loans and deposits.
    It serves as an indicator of the cost of unsecured overnight borrowing.
    """
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


def get_ruonia_overnight(cbr_client,
                         first_date: Optional[str] = None,
                         last_date: Optional[str] = None,
                         period: str = 'D') -> pd.Series:
    """
    Get RUONIA overnight value time series.

    RUONIA (Ruble Overnight Index Average) is the weighted average interest rate on interbank loans and deposits.
    It serves as an indicator of the cost of unsecured overnight borrowing.
    """
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
    return squeeze_df(df, period, 'RUONIA.RATE')


def squeeze_df(df, period, symbol):
    s = df.squeeze()
    s.index = s.index.astype('period[D]', copy=False)
    s = pad_missing_periods(s)
    s.index.rename('date', inplace=True)
    if period.upper() == 'M':
        s = s.resample('M').last()
    return s.rename(symbol)


def guess_date(input_date, default_value):
    """
    Create data in datetime format.
    CBR accepts "%Y-%m-%d" format only.
    """
    if input_date:
        try:
            date = datetime.strptime(input_date, "%Y-%m-%d")
        except ValueError:
            date = datetime.strptime(input_date, "%Y-%m")
    else:
        date = datetime.strptime(default_value, "%Y-%m-%d")
    return date
