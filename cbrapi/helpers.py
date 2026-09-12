from datetime import datetime, date
import pandas as pd


def pad_missing_periods(
    ts: pd.Series | pd.DataFrame,
    freq: str = "D",
    end_date: date | None = None,
    max_gap: int | None = None,
) -> pd.Series | pd.DataFrame:
    """
    Pad missing dates and values in the time series.

    `max_gap` limits the padding: two consecutive observations more than `max_gap` periods
    of `freq` apart keep the gap between them, and the series is extended to `end_date`
    only when the last observation is within `max_gap` periods of it. By default (None)
    every gap is padded.
    """
    if ts.empty:
        return ts
    name = ts.index.name
    if not isinstance(ts.index, pd.PeriodIndex):
        ts.index = ts.index.to_period(freq)
    ts.sort_index(ascending=True, inplace=True)  # The order should be ascending to make new Period index
    observations = ts.index
    end = observations[-1]
    if end_date:
        end_period = pd.Period(end_date, freq=freq)
        if end_period > end and (max_gap is None or (end_period - end).n <= max_gap):
            end = end_period
    idx = _periods_to_pad(observations, end, freq, max_gap)
    ts = ts.reindex(idx, method="pad")
    ts.index.rename(name, inplace=True)
    return ts


def _periods_to_pad(
    observations: pd.PeriodIndex, end: pd.Period, freq: str, max_gap: int | None
) -> pd.PeriodIndex:
    """
    Build the index to pad the time series to: every period from the first observation to
    `end`, minus the gaps longer than `max_gap`.

    Observations separated by more than `max_gap` periods start a new segment; each segment
    is covered continuously and nothing is placed between them.
    """
    if max_gap is None:
        return pd.period_range(start=observations[0], end=end, freq=freq)
    ordinals = observations.asi8  # ordinals count freq periods, so their difference is the gap
    idx = pd.PeriodIndex([], freq=freq)
    segment_start = observations[0]
    for position in range(1, len(ordinals)):
        if ordinals[position] - ordinals[position - 1] > max_gap:
            idx = idx.append(pd.period_range(start=segment_start, end=observations[position - 1], freq=freq))
            segment_start = observations[position]
    return idx.append(pd.period_range(start=segment_start, end=end, freq=freq))


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
                if pd.api.types.is_string_dtype(data[col]):
                    data[col] = data[col].str.split("T").str[0]

                data.index = pd.to_datetime(data[col], utc=False)
                data.index.name = "DATE"
                data.drop(col, axis=1, inplace=True)
                break
    return data


def remove_unnecessary_columns(data):
    """
    Remove unnecessary columns from DataFrame.
    """
    data.drop(
        columns=[col for col in ["id", "rowOrder", "vol", "DateUpdate"] if col in data.columns],
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
        data = data.groupby([data.index, "p1"])[["d1", "d7", "d30", "d90"]].first().unstack(level="p1")
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
        data = data.squeeze(axis=1)

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


def check_ticker_code(ticker, symbol_col):
    """
    Check ticker for currency.
    """
    if "." in ticker:
        raise ValueError("Currency ticker should not contain dots.")

    if (len(ticker) < 3 or len(ticker) > 3) and "RUB" not in ticker:
        raise ValueError("Currency ticker should be 3 characters (e.g., 'USD').")

    ticker = ticker[:3]

    if ticker not in symbol_col.values:
        raise ValueError(f"API Central Bank does not support  this ticker: {ticker}.")

    return ticker


def check_symbol_ts(symbol, symbol_col):
    """
    Check symbol for currency.
    """

    if "." in symbol:
        raise ValueError("Currency symbols should not contain dots.")

    if len(symbol) < 3 or len(symbol) > 6:
        raise ValueError(
            f"Symbol '{symbol}' has invalid length ({len(symbol)} characters). "
            f"Currency symbols should be 3 characters (e.g., 'USD') or 6 characters for RUB pairs only (e.g., 'USDRUB', 'RUBUSD')."
        )

    currency_pair = symbol[:6]
    first_currency = currency_pair[:3]
    second_currency = currency_pair[3:]

    if len(symbol) == 6:
        if "RUB" not in [first_currency, second_currency]:
            if first_currency in symbol_col.values and second_currency in symbol_col.values:
                raise ValueError(f"API does not support cross courses. Detected: {first_currency}/{second_currency}")

    if symbol not in symbol_col.values and "RUB" not in [
        first_currency,
        second_currency,
    ]:
        raise ValueError(f"API Central Bank does not support  this symbol: {symbol}.")
