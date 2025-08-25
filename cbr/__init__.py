from importlib.metadata import version


from cbr.cbr_settings import make_cbr_client
from cbr.currency import get_currencies_list, get_currency_code, get_time_series
from cbr.helpers import pad_missing_periods, calculate_inverse_rate
from cbr.ruonia import get_ruonia_ts, get_ruonia_index, get_ruonia_overnight, squeeze_df, guess_date


# __version__ = version("cbr")
