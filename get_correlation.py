from dragons import *

acc = Account(API_KEY)

with open('symbols_list.txt', 'r') as r:
    symbols = ''.join(r.readlines()).replace('\n',' ').split(' ')

print_correlation(symbols)