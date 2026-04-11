import pytest
import pandas as pd

from cbrapi.currency import get_currencies_list
from cbrapi.cbr_settings import make_cbr_client


@pytest.fixture(autouse=True)
def clear_lru_caches():
    """Clear lru_cache before and after each test to prevent cross-test contamination."""
    get_currencies_list.cache_clear()
    make_cbr_client.cache_clear()
    yield
    get_currencies_list.cache_clear()
    make_cbr_client.cache_clear()


@pytest.fixture
def currencies_df():
    """Minimal currencies DataFrame matching CBR format."""
    return pd.DataFrame(
        {
            "Vcode": ["R01235", "R01239"],
            "Vnom": [1, 1],
            "VcharCode": ["USD", "EUR"],
            "VunitRate": [1, 1],
        }
    )
