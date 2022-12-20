from dragons import *
import time

acc = Account(API_KEY)

def print_correlation(symbol_list):
    while(True):
        account = Account(API_KEY)
        x = symbol_list[0]
        if x:
            test_list = symbol_list.copy()
            s1 = Symbol(x, account)
            test_list.remove(x)
            ret = [f'{s1.name}, {y}, {s1.check_correlation(Symbol(y, account))}' for y in test_list if y]
            ret = '\n'.join(ret)
            print(ret)
            with open('all_correlations.txt','a') as w:
                w.write(f'{ret}\n')
        symbol_list.remove(x)
        if len(symbol_list) == 0:
            break
        time.sleep(1) # to prevent ratelimiting measures from oanda

with open('symbols_list.txt', 'r') as r:
    symbols = ''.join(r.readlines()).replace('\n',' ').split(' ')

print_correlation(symbols)