import cbr

print(cbr.currency.get_currencies_list())

client = cbr.make_cbr_client()

#print(client)

print(cbr.get_ruonia_index(client))

print(cbr.currency.get_currencies_list())

print(cbr.currency.get_currency_code("USDRUB"))

print(cbr.currency.get_time_series(symbol="USDRUB", first_date="2019-01-01", last_date="2020-12-31", period="M"))
