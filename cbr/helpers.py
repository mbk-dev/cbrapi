from typing import Union

import pandas as pd


def pad_missing_periods(ts: Union[pd.Series, pd.DataFrame], freq: str = 'D') -> Union[pd.Series, pd.DataFrame]:
    """
    Pad missing dates and values in the time series.
    """
    name = ts.index.name
    if not isinstance(ts.index, pd.PeriodIndex):
        ts.index = ts.index.to_period(freq)
    ts.sort_index(ascending=True, inplace=True)  # The order should be ascending to make new Period index
    idx = pd.period_range(start=ts.index[0], end=ts.index[-1], freq=freq)
    ts = ts.reindex(idx, method='pad')
    ts.index.rename(name, inplace=True)
    return ts


def calculate_inverse_rate(close_ts):
    """
    Inverse close values for currency rate data.
    """
    return 1. / close_ts
