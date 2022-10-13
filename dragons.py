import json
import copy
import requests

api_key = '' 
with open('api.key','r') as f:
    api_key = f.readlines()[0].replace('\n','')


class Account:
    def __init__(self,api_key):
        self.api_key    = api_key
        self.base_url   = 'https://api-fxpractice.oanda.com/v3'
        self.headers    = {'Authorization':f'Bearer {self.api_key}'}
        self.account_id = self.get_accounts().json()['accounts'][0]['id']

    def get_accounts(self):
        url = self.base_url + '/accounts'
        response = requests.get(url,headers=self.headers)
        return(response)

    def get_instruments(self):
        url = f'{self.base_url}/accounts/{self.account_id}/instruments' 
        response = requests.get(url,headers=self.headers)
        return(response)


class Instrument(Account):
    def __init__(self, name, **kwargs):
        super().__init__(kwargs['api_key'])
        self.name = name
        self.price = self.get_price()         
    
    def get_price(self):
        url = f'{self.base_url}/accounts/{self.account_id}/instruments/{self.name}/candles'
        headers = copy.deepcopy(self.headers)
        headers['Accept-Datetime-Format'] = 'RFC3339'
        params = {'price':'B', 'granularity':'D', 'count':'2'}
        response = requests.get(url,headers=headers,params=params)
        return(response)
 
            
class OrderRequest(Account):
    def __init__(self, **kwargs):
        super().__init__(kwargs['api_key'])
        self.price              = kwargs['price']
        self.stop_loss          = kwargs['stop_loss']
        self.price_bound        = kwargs['price_bound']
        self.position_symbol    = kwargs['position_symbol']
        self.position_volume    = kwargs['position_volume']
    
    def send(self):
        self.url += f'/{self.account_id}/orders'
        headers = copy.deepcopy(self.headers)
        headers['Accept-Datetime-Format'] = 'RFC3339'
        order_request_dict = {
            'instrument'        : f'({position_symbol})',
            'units'             : f'({position_volume})',   # note that 
            # positive unit values are interpreted as a buy order and 
            # negative unit values are interpreted as a sell order
            'priceBound'        : f'({priceValue})',        # priceBound 
            # indicates the worst price that the order will execute at
            'positionFill'      : f'(OPEN_ONLY)',
            'stopLossOnFill'    : {'price':f'{stop_loss}'}
        }
        data = json.dumps(order_dict)
        return(requests.post(url,headers=headers,data=data))
 
if __name__ == "__main__":
    prices = Instrument('EUR_USD', api_key=api_key)
    print(prices.price.text)
       
