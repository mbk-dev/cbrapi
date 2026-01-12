import cbrapi as cbr

print(cbr.currency.get_currencies_list())

print(cbr.get_ruonia_ts(symbol="RUONIA"))

print(cbr.get_ruonia_index())

print(cbr.currency.get_currencies_list())

print(cbr.currency.get_currency_code("USDRUB"))

print(
    cbr.currency.get_time_series(
        symbol="USDRUB", first_date="2025-12-01", last_date="2026-01-31", period="D"
    )
)

print(cbr.get_ruonia_overnight())

print(cbr.get_key_rate("2017-09-13", "2023-09-13"))

print(cbr.get_metals_prices())

print(cbr.get_mrrf("2015-01", "2022-01"))

print(cbr.get_ibor())

print(cbr.get_roisfix())

print(cbr.get_currencies_list())

print(cbr.get_currency_code("USDRUB"))
