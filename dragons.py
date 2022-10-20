import copy
import json
import math
import pprint

import pandas as pd
import requests
from ta.utils import dropna
from ta.volatility import AverageTrueRange
from ta.trend import SMAIndicator
from ta.trend import ADXIndicator

# TODO
#   - pull historical price data for entries and exits 

api_key = '' 

with open('api.key','r') as f:
    api_key = f.readlines()[0].replace('\n','')


class Account:
    def __init__(self,api_key,live=False,account_id=None):
        self.api_key    = api_key
        self.base_url   = 'https://api-fxpractice.oanda.com/v3'
        if live == True:
            self.base_url   = 'https://api-fxtrade.oanda.com/v3'
        self.headers    = {'Authorization':f'Bearer {self.api_key}'}
        self.account_id = self.get_id()
        if account_id != None:
            self.account_id = account_id
        self.currency   = self.get_summary()['account']['currency']

    def get_id(self):
        url = self.base_url + '/accounts'
        response = requests.get(url,headers=self.headers)
        return(response.json())['accounts'][0]['id']

    def get_summary(self):
        url = f'{self.base_url}/accounts/{self.account_id}/summary'
        headers = self.headers
        headers['Accept-Datetime-Format'] = 'RFC3339'
        response = requests.get(url,headers=self.headers)
        return(response.json())
        
    def get_instruments(self):
        url = f'{self.base_url}/accounts/{self.account_id}/instruments' 
        response = requests.get(url,headers=self.headers)
        return(response)


class Instrument(Account):
    '''Instrument class that contains information relating to the Instrument selected.
       Takes position arguments name of symbol, and keyword arguments api_key.'''
    def __init__(self, name, **kwargs):
        super().__init__(kwargs['api_key'])
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
        url = f'{self.base_url}/accounts/{self.account_id}/instruments'
        headers = copy.deepcopy(self.headers)
        params = {'instruments':f'{self.name}'}
        response = requests.get(url,headers=headers,params=params)
        return(response.json()['instruments'][0])
    
    def get_candles(self,count=1):
        url = f'{self.base_url}/accounts/{self.account_id}/instruments/{self.name}/candles'
        headers = copy.deepcopy(self.headers)
        headers['Accept-Datetime-Format'] = 'RFC3339'
        params = {'price':'B', 'granularity':'D', 'count':f'{count}'}
        response = requests.get(url,headers=headers,params=params)
        return(response.json()['candles'])
    
    def get_ohlc(self, number_of_periods=100):
        '''Takes a number of periods and returns a pandas datafram of ohlc data with timestamp'''
        open_list   = []
        high_list   = []
        low_list    = []
        close_list  = []
        time_list   = []

        for x in self.get_candles(count=number_of_periods):
            open_list.append(float(x['bid']['o']))
            high_list.append(float(x['bid']['h']))
            low_list.append(float(x['bid']['l']))
            close_list.append(float(x['bid']['c']))
            time_list.append(x['time'])
        open_series     = pd.Series(open_list,index=time_list, name='open')
        high_series     = pd.Series(high_list,index=time_list, name='high')
        low_series      = pd.Series(low_list,index=time_list, name='low')
        close_series    = pd.Series(close_list,index=time_list, name='close')
        
        df = pd.concat([open_series.to_frame(), high_series, low_series, close_series], axis=1) 
        return(df) 
        
    def get_adx(self, number_of_periods=40):
        df = self.get_ohlc() 
        adx_indicator = ADXIndicator(high=df['high'],
                                        low=df['low'],
                                        close=df['close'],
                                        window=18)
        return(adx_indicator.adx())
 
    def get_atr(self, number_of_periods=40):
        df = self.get_ohlc()
        atr_indicator = AverageTrueRange(high=df['high'], 
                                            low=df['low'], 
                                            close=df['close'], 
                                            window=18)
        return(atr_indicator.average_true_range())
            

class OrderRequest(Account):
    '''Creates OrderRequest object that takes params and returns order request object to be sent to the server. 
       Takes arguments api_key, instrument, and position_volume where:
            - api_key is the key provided by Oanda for the account
            - instrument is an instrument object defined above
            - open_price is the price at which to open the order
            - initial_risk is the distance to set the stop loss from the open price'''
    def __init__(self, **kwargs):
        super().__init__(kwargs['api_key'])
        self.open_price         = float(symbol.price)
        self.position_symbol    = kwargs['instrument'].name
        self.position_volume    = kwargs['position_volume']
        if self.position_volume > 0:
            self.stop_loss_price = round(self.open_price - kwargs['initial_risk'], 
                                            kwargs['instrument'].display_precision)
            self.price_bound = self.open_price + (kwargs['instrument'].pip * 3)
        if self.position_volume < 0: 
            self.stop_loss_price = round(self.open_price + kwargs['initial_risk'],
                                            kwargs['instrument'].display_precision)
            self.price_bound = self.open_price - (kwargs['instrument'].pip * 3)
    
    def send(self):
        '''Sends the order to the server for processing'''
        url = f'{self.base_url}/accounts/{self.account_id}/orders'
        headers = copy.deepcopy(self.headers)
        headers['Accept-Datetime-Format'] = 'RFC3339'
        order_request_dict = {
            'order' : {
                'type'              : f'MARKET',
                'instrument'        : f'{self.position_symbol}',
                'units'             : f'{self.position_volume}',   
                # note: 
                # positive unit values are interpreted as a buy order and 
                # negative unit values are interpreted as a sell order
                'priceBound'        : f'{self.price_bound}',        
                # priceBound 
                # indicates the worst price that the order will execute at
                'positionFill'      : f'OPEN_ONLY',
                'stopLossOnFill'    : {'price':f'{self.stop_loss_price}'}}}
        data = json.dumps(order_request_dict)
        return(requests.post(url,headers=headers,json=order_request_dict))
    

class PositionSize:
    def __init__(self, **kwargs):
        '''Takes keyword arguments instrument, percent_risk, risk_pips where:
            - instrument is the object defined above
            - account is the object defined above
            - percent_risk is percentage of account balance to be risked on each trade
            - risk_pips is the amount of risk taken in pips'''
        self.instrument = kwargs['instrument']
        self.account = kwargs['account']
        self.percent_risk = kwargs['percent_risk']
        self.risk_pips = kwargs['risk_pips']

        dollars_risked = self.percent_risk * float(self.account.get_summary()['account']['balance'])
        converted_dollars_risked = dollars_risked * self.get_conversion_rate() 
        initial_risk_pips = self.risk_pips / self.instrument.pip
        initial_risk_dollars = self.instrument.pip * initial_risk_pips
        size_rounded = round(
            converted_dollars_risked / initial_risk_dollars,
            self.instrument.trade_unit_precision)

        self.size = float(converted_dollars_risked / initial_risk_dollars)
        if self.size < size_rounded:
            self.size = size_rounded - self.instrument.min_trade_size
        elif self.size >= size_rounded:
            self.size = size_rounded 
        if self.size < self.instrument.min_trade_size:
            raise ValueError('position size came in under min_trade_size')
        if not kwargs['is_buy']:
            self.size *= -1

    def get_conversion_rate(self):
        conversion_rate = 0
        if self.instrument.base_currency == self.account.currency:
            conversion_factor = 1
        else:
            try:
                symbol = Instrument(
                    f'{self.account.currency}_{self.instrument.quote_currency}',
                    api_key=account.api_key)
            except KeyError as exc:
                pass
                try:
                    symbol = Instrument(
                        f'{self.instrument.quote_currency}_{self.account.currency}',
                        api_key=account.api_key)
                except KeyError as exc:
                    print(exc)
                else:
                    conversion_rate = 1/float(symbol.price)
            else:
                conversion_rate = float(symbol.price)
        return(conversion_rate)


class Entry:
    def channel_breakout(**kwargs):
        if kwargs['adx'][-2] > 25 and kwargs['ohlc']['close'].max() == kwargs['ohlc']['close'][-1]:
            #buy 
            pass
        elif kwargs['adx'][-2] > 25 and kwargs['ohlc']['close'].min() == kwargs['ohlc']['close'][-1]:
            #sell
            pass
    
 
if __name__ == "__main__":
    account = Account(api_key)
    symbol = Instrument('EUR_USD', api_key=api_key)
    initial_risk = symbol.last_atr

    units = PositionSize(
        instrument=symbol, 
        account=account, 
        risk_pips=initial_risk, 
        percent_risk=0.01,
        is_buy=False).size

    order = OrderRequest(
        api_key = api_key,
        open_price = symbol.price,
        initial_risk = initial_risk,
        instrument = symbol,
        position_volume = units)
    
    ohlc = symbol.get_ohlc(40)
    
