from importlib.metadata import version


from cbrapi.cbr_settings import make_cbr_client
from cbrapi.currency import get_currencies_list, get_currency_code, get_time_series
from cbrapi.helpers import (
    pad_missing_periods,
    calculate_inverse_rate,
    normalize_data,
    guess_date,
)
from cbrapi.ruonia import (
    get_ruonia_ts,
    get_ruonia_index,
    get_ruonia_overnight,
    get_roisfix,
)
from cbrapi.rates import get_key_rate, get_ibor
from cbrapi.metals import get_metals_prices
from cbrapi.reserves import get_mrrf


# __version__ = version("cbr")
