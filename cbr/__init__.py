from importlib.metadata import version


from cbr.cbr_settings import make_cbr_client
from cbr.currency import get_currencies_list, get_currency_code, get_time_series
from cbr.helpers import pad_missing_periods, calculate_inverse_rate, normalize_data, guess_date
from cbr.ruonia import get_ruonia_ts, get_ruonia_index, get_ruonia_overnight, get_ruoniasv, get_roisfix
from cbr.rates import get_key_rate, get_ibor
from cbr.metals import get_metals_prices
from cbr.reserves import get_mrrf


# __version__ = version("cbr")
