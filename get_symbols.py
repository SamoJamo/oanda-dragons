from dragons import Account, API_KEY

symbols = Account(API_KEY).get_symbols().json()

for symbol in symbols['instruments']:
    print(symbol['name'])