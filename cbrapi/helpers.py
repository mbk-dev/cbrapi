from typing import Union
from datetime import datetime, date
import pandas as pd


def pad_missing_periods(
    ts: Union[pd.Series, pd.DataFrame], freq: str = "D"
) -> Union[pd.Series, pd.DataFrame]:
    """
    Pad missing dates and values in the time series.
    """
    name = ts.index.name
    if not isinstance(ts.index, pd.PeriodIndex):
        ts.index = ts.index.to_period(freq)
    ts.sort_index(
        ascending=True, inplace=True
    )  # The order should be ascending to make new Period index
    idx = pd.period_range(start=ts.index[0], end=ts.index[-1], freq=freq)
    ts = ts.reindex(idx, method="pad")
    ts.index.rename(name, inplace=True)
    return ts


def calculate_inverse_rate(close_ts):
    """
    Inverse close values for currency rate data.
    """
    return 1.0 / close_ts


def set_datetime_index(data):
    """
    Set datetime index for DataFrame by detecting date columns.
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        for col in data.columns:
            if any(keyword in str(col) for keyword in ["CDate", "DateMet", "D0", "DT"]):
                data[col].str.split("T").str[0]
                data.index = pd.DatetimeIndex(
                    pd.to_datetime(data[col], utc=True)
                ).tz_convert(None)
                data.index.name = "DATE"
                data.drop(col, axis=1, inplace=True)
                break
    return data


def remove_unnecessary_columns(data):
    """
    Remove unnecessary columns from DataFrame.
    """
    data.drop(
        columns=[
            col
            for col in ["id", "rowOrder", "vol", "DateUpdate"]
            if col in data.columns
        ],
        inplace=True,
    )
    return data


def unstack_groups(data, symbol):
    """
    Unstack grouped data based on symbol type.
    """
    if symbol == "DrgMet":
        data = data.groupby([data.index, "CodMet"])["price"].first().unstack()
        data.columns.name = None

    if symbol == "MKR":
        data = (
            data.groupby([data.index, "p1"])[["d1", "d7", "d30", "d90", "d180", "d360"]]
            .first()
            .unstack(level="p1")
        )
        data.columns = data.columns.rename(None, level=1)
        data.columns.name = None

    return data


def column_rename(data, level_0, level_1):
    """
    Rename columns based on mapping dictionaries.
    """
    if isinstance(data.columns, pd.MultiIndex):
        if level_0:
            new_level_0 = data.columns.levels[0].map(lambda x: level_0.get(str(x), x))
            data.columns = data.columns.set_levels(new_level_0, level=0)

        if level_1:
            new_level_1 = data.columns.levels[1].map(lambda x: level_1.get(str(x), x))
            data.columns = data.columns.set_levels(new_level_1, level=1)

    else:
        if level_1 and isinstance(level_1, dict):
            data = data.rename(columns=level_1)
            available_columns = [col for col in level_1.values() if col in data.columns]
            data = data[available_columns] if available_columns else data

        else:
            if level_1 and not isinstance(level_1, dict):
                if len(data.columns) == 1:
                    data = data.rename(columns={data.columns[0]: str(level_1)})
    return data


def normalize_data(data, period, level_0=None, level_1=None, symbol=None):
    """
    Normalize time series data through multiple processing steps.
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()

    set_datetime_index(data)

    remove_unnecessary_columns(data)

    data = unstack_groups(data, symbol)

    data = column_rename(data, level_0, level_1)

    data = pad_missing_periods(data)

    if period.upper() == "M":
        data = data.resample("M").last()

    if len(data.columns) == 1:
        data = data.squeeze()

    return data


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
