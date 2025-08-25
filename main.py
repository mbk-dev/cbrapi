import cbr

print(cbr.currency.get_currencies_list())

client = cbr.make_cbr_client()

#print(client)

print(cbr.get_ruonia_index(client))
