import time
import pprint
import logging as lg

import pandas as pd
import requests
from ta.volatility import AverageTrueRange
from ta.trend import ADXIndicator

# TODO
#   - test Trade object to accept trade data from get_open_orders
#   - write docstrings for all classes and methods
#   - response exception handling:
#       - 200 good
#       - 400 bad
#       - 500 real bad

API_KEY = ''
lg.basicConfig(filename='dragons.log', level=lg.WARNING)

with open('api.key','r',encoding='utf-8') as f:
    API_KEY = f.readlines()[0].replace('\n','')


class ResponseError(Exception):
    pass

class InstrumentError(Exception):
    pass

class Account:
    def __init__(self, api_key,live=False,account_id=None):
        self.api_key    = api_key
        self.base_url   = 'https://api-fxpractice.oanda.com/v3'
        if live == True:
            self.base_url   = 'https://api-fxtrade.oanda.com/v3'
        self.headers    = { 'Authorization': f'Bearer {self.api_key}',
                            'Accept-Datetime-Format': 'RFC3339'}
        self.account_id = self.get_id()
        if account_id is not None:
            self.account_id = account_id
        self.currency   = self.get_summary().json()['account']['currency']

    def get_id(self):
        url = f'{self.base_url}/accounts'
        response = requests.get(url,headers=self.headers, timeout=10)
        return(response.json())['accounts'][0]['id']

    def get_summary(self):
        url = f'{self.base_url}/accounts/{self.account_id}/summary'
        response = requests.get(url,headers=self.headers, timeout=10)
        return(response)
        
    def get_symbols(self):
        """ Return the response to a requested list of symbols enabled for trading on this account"""
        url = f'{self.base_url}/accounts/{self.account_id}/instruments' 
        response = requests.get(url,headers=self.headers, timeout=10)
        return(response)
   
    def get_open_trades(self):
        url = f'{self.base_url}/accounts/{self.account_id}/openTrades' 
        response = requests.get(url,headers=self.headers, timeout=10)
        return(response)


class Symbol:
    """Symbol class that contains information relating to the Symbol selected.
    Takes position arguments name of symbol, and keyword arguments account."""
    def __init__(self, name, account):
        self.account = account
        self.name = name
        self.price = self.get_candles()[0]['bid']['c']
        details = self.get_details()
        self.pip_location = details['pipLocation']
        self.pip = 1 * 10 ** self.pip_location 
        self.base_currency = details['name'].split('_')[0]
        self.quote_currency = details['name'].split('_')[1]
        self.min_trade_size = float(details['minimumTradeSize'])
        self.trade_unit_precision = int(details['tradeUnitsPrecision'])
        self.display_precision = int(details['displayPrecision'])
        self.last_atr = self.get_atr()[-2]

    def get_details(self):
        url = f'{self.account.base_url}/accounts/{self.account.account_id}/instruments'
        params = {'instruments':f'{self.name}'}
        response = requests.get(url,headers=self.account.headers,params=params, timeout=10)
        return(response.json()['instruments'][0])
    
    def get_candles(self,count=1):
        url = f'{self.account.base_url}/accounts/{self.account.account_id}/instruments/{self.name}/candles'
        params = {'price':'B', 'granularity':'D', 'count':f'{count}'}
        response = requests.get(url,headers=self.account.headers,params=params, timeout=10)
        if response.status_code != 200:
            lg.warning(response.json()['errorMessage'])
            print(response.json()['errorMessage'])
            return(None)
        else:
            return(response.json()['candles'])
    
    def get_ohlc(self, number_of_periods=100):
        """Takes a number of periods and returns a pandas dataframe 
        of ohlc data with timestamp"""
        open_list   = []
        high_list   = []
        low_list    = []
        close_list  = []
        time_list   = []

        candle_response = self.get_candles(count=number_of_periods)
        if candle_response is None:
            return None
        for x in candle_response:
            open_list.append(float(x['bid']['o']))
            high_list.append(float(x['bid']['h']))
            low_list.append(float(x['bid']['l']))
            close_list.append(float(x['bid']['c']))
            time_list.append(x['time'])
        open_series     = pd.Series(open_list, index=time_list, 
                                    name='open')
        high_series     = pd.Series(high_list, index=time_list, 
                                    name='high')
        low_series      = pd.Series(low_list, index=time_list, 
                                    name='low')
        close_series    = pd.Series(close_list,
                                    index=time_list, name='close')
        df = pd.concat([open_series.to_frame(), 
                        high_series, 
                        low_series, 
                        close_series], axis=1) 
        return(df) 
        
    def get_adx(self):
        """Return the ADX with default period 18"""
        df = self.get_ohlc() 
        adx_indicator = ADXIndicator(
                            high=df['high'],
                            low=df['low'],
                            close=df['close'],
                            window=18)
        return(adx_indicator.adx())
 
    def get_atr(self):
        """Return the ATR with default period 18"""
        df = self.get_ohlc()
        atr_indicator = AverageTrueRange(
                            high=df['high'], 
                            low=df['low'], 
                            close=df['close'], 
                            window=18)
        return(atr_indicator.average_true_range())

    def check_correlation(self, sym2):
        """Return the correlation between the close price of the Symbol object and another symbol over the past 100 periods"""
        return(self.get_ohlc()['close'].corr(sym2.get_ohlc()['close']))


class PositionSize:
    def __init__(self, **kwargs):
        """Takes keyword arguments symbol, percent_risk 
        and risk_pips where:
            - symbol is the object defined above
            - account is the object defined above
            - percent_risk is percentage of account balance to be 
                risked on each trade
            - risk_pips is the amount of risk taken in pips"""
        self.symbol = kwargs['symbol']
        self.account = kwargs['account']
        self.percent_risk = kwargs['percent_risk']
        self.risk_pips = kwargs['risk_pips']
        
        account_balance = float(self.account.get_summary().json()['account']['balance'])
        dollars_risked = self.percent_risk * account_balance 
        converted_dollars_risked = dollars_risked * self.get_conversion_rate() 
        initial_risk_pips = self.risk_pips / self.symbol.pip
        initial_risk_dollars = self.symbol.pip * initial_risk_pips
        size_rounded = round(
            converted_dollars_risked / initial_risk_dollars,
            self.symbol.trade_unit_precision)

        self.size = float(converted_dollars_risked / initial_risk_dollars)
        if self.size < size_rounded:
            self.size = size_rounded - self.symbol.min_trade_size
        elif self.size >= size_rounded:
            self.size = size_rounded 
        if self.size < self.symbol.min_trade_size:
            raise ValueError('position size came in under min_trade_size')
        if not kwargs['is_buy']:
            self.size *= -1

    def get_conversion_rate(self):
        """Using the self.symbol and self.account attributes,
        returns the conversion rate between the account currency and
        trade quote currency
        """
        conversion_rate = 0
        if self.symbol.base_currency == self.account.currency:
            conversion_rate = 1
        else:
            try:
                symbol = Symbol(
                    f'{self.account.currency}_{self.symbol.quote_currency}',
                    self.account)
            except KeyError as exc:
                try:
                    symbol = Symbol(
                        f'{self.symbol.quote_currency}_{self.account.currency}',
                        self.account)
                except KeyError as exc:
                    lg.error(exc)
                    print(exc)
                else:
                    conversion_rate = 1/float(symbol.price)
            else:
                conversion_rate = float(symbol.price)
        return(conversion_rate)

class Trade:
    """Creates Trade object that takes params and returns order request object 
    to be sent to the server. 
    Takes arguments api_key, initial_risk, symbol and position_volume where:
        - api_key is the key provided by Oanda for the account
        - initial_risk is the distance to set the stop loss from the open price
        - symbol is an symbol object defined above
        - position_volume is a size derived from PositionSize object below
    """
            
    def __init__(self, account, **kwargs):
        self.account            = account
        self.symbol             = Symbol(kwargs['symbol'],self.account)
        self.position_volume    = float(kwargs['position_volume'])
        self.open_price         = float(kwargs.get('open_price', self.symbol.price))
        self.trade_id           = kwargs.get('trade_id', None)
        self.open_time          = kwargs.get('openTime', None)
        self.stop_loss_price    = float(kwargs.get('stop_loss_price', None))
        self.profit_amount      = float(kwargs.get('profit_amount', None))
        self.commission_amount  = float(kwargs.get('commission_amount', None))
        self.swap_amount        = float(kwargs.get('swap_amount', None))
        self.stop_loss_id       = kwargs.get('stop_loss_id', None)
        self.initial_risk       = float(kwargs.get(
                                            'initial_risk', 
                                            abs(float(self.open_price)
                                            - float(self.stop_loss_price))))
    
        if self.position_volume > 0:
            self.stop_loss_price = round(self.open_price - self.initial_risk, 
                                        self.symbol.display_precision)
            self.price_bound = self.open_price + (self.symbol.pip * 3)
        if self.position_volume < 0: 
            self.stop_loss_price = round(self.open_price + self.initial_risk,
                                        self.symbol.display_precision)
            self.price_bound = self.open_price - (self.symbol.pip * 3)

    @classmethod
    def from_json(cls, account, trade_json):
        """Create a Trade object from a json,
        useful for pulling trade data from server"""
        retval = cls(
            account,
            symbol=trade_json['instrument'],
            position_volume=trade_json['initialUnits'],
            open_price =trade_json['price'],
            trade_id=trade_json['id'],
            open_time=trade_json['openTime'],
            stop_loss_price=trade_json['stopLossOrder']['price'],
            profit_amount=trade_json['unrealizedPL'],
            commission_amount=trade_json['financing'],
            swap_amount=trade_json['dividendAdjustment'],
            stop_loss_id=trade_json['stopLossOrder']['id'])
        return(retval)
    
    def open(self):
        """Send the order to the server for processing"""
        url = f'{self.account.base_url}/accounts/{self.account.account_id}/orders'
        order_request_dict = {
            'order' : {
                'type'              : 'MARKET',
                'instrument'        : f'{self.symbol.name}',
                'units'             : f'{self.position_volume}',  
                'priceBound'        : f'{self.price_bound}',       
                # ^ indicates the worst price that the order will execute at
                'positionFill'      : 'OPEN_ONLY',
                'stopLossOnFill'    : {'price' : f'{self.stop_loss_price}'}}}
        return(requests.post(url, headers=self.account.headers, json=order_request_dict))

    def close(self):
        """Close the specified order"""
        url = f'{self.account.base_url}/accounts/{self.account.account_id}/trades/{self.trade_id}/close'
        return(requests.put(url, headers=self.account.headers))


class Entry:
    """Class containing entry criteria functions"""
    def channel_breakout(symbol):
        """ Take a Symbol object and return either a string
            indicating whether to enter on the buy or sell side
            or None if no entry is found.
        """
        adx = symbol.get_adx()
        ohlc = symbol.get_ohlc()
        if adx[-2] > 25 and ohlc['close'].max() == ohlc['close'][-1]:
            #buy 
            return 'buy entry'
        elif adx[-2] > 25 and ohlc['close'].min() == ohlc['close'][-1]:
            #sell
            return 'sell entry'
        else:
            return None


class Exit:
    """Class containing exit criteria functions"""
    def trailing_period_close(account, trade, periods=40):
        """ Takes a trade, account and period and checks the lowest
            and highest price for those times. If the largest adverse
            price of n periods occurred in the most recent period,
            returns True, else False
        """
        retval = False
        logval = ''
        ohlc = trade.symbol.get_ohlc()
        if  (ohlc['close'].max() == ohlc['close'][-1]
            and trade.position_volume < 0):
            logval = f'Close signal for sell trade with trade id {trade["id"]} sent.'
            retval = True 
        elif (ohlc['close'].min() == ohlc['close'][-1]
            and trade.position_volume > 0):
            logval = f'Close signal for buy trade with trade id {trade["id"]} sent.'
            retval = True 
        elif trade.position_volume == 0:
            logval = f'Something has gone wrong. Trade id {trade["id"]} has position size of 0'
            retval = False 
        if logval:
            lg.info(logval)
            print(logval)
        return retval


def on_tick_loop():
    list_of_symbols = ['UK100_GBP', 'SPX500_USD', 'NAS100_USD', 'USD_JPY', 'EUR_USD', 'BCO_USD', 'NATGAS_USD', 'WHEAT_USD', 'SOYBN_USD', 'SUGAR_USD', 'ETH_USD', 'XAU_USD', 'XAG_USD', 'GBP_USD']

    #list_of_symbols = [ 'EUR_USD', 'ETH_USD', 'USD_JPY', 'BTC_USD',
    #                    'WTICO_USD', 'GBP_USD', 'NATGAS_USD',
    #                   'SPX500_USD']

    account = Account(API_KEY)

    for trade in account.get_open_trades().json()['trades']:
        trade_obj = Trade.from_json(account,trade)

        if Exit.trailing_period_close(account, trade_obj):
            symbol = Symbol(trade['instrument'], account)
            initial_risk = symbol.last_atr

            units = PositionSize(
                symbol=symbol,
                account=account,
                risk_pips=initial_risk,
                percent_risk=0.01,
                is_buy=False).size

            position = Trade.from_request(account,trade)

    for name in list_of_symbols:
        symbol = Symbol(name, account)
        logval = ''
        if Entry.channel_breakout(symbol) == None:
            logval = f'No new entry for symbol {name}'
            print(logval)
            lg.info(logval)
            continue
        elif Entry.channel_breakout(symbol) == 'buy entry':
            is_buy = True
        elif Entry.channel_breakout(symbol) == 'sell entry':
            is_buy = False

        initial_risk = symbol.last_atr

        units = PositionSize(
            account=account,
            symbol=symbol,
            risk_pips=initial_risk,
            percent_risk=0.01,
            is_buy=is_buy).size

        order = Trade(
            account,
            open_price=symbol.price,
            initial_risk=initial_risk,
            symbol=symbol,
            position_volume=units)

        pprint.pp(order.send())
        #lg.info(f'New trade sent, ticket {order.send}')

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


if __name__ == '__main__':
    on_tick_loop()