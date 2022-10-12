import requests

class Account:
    def __init__(self,**kwargs):
        self.api_key    = None
        self.account_id = None
        if api_key in kwargs:
            self.api_key = api_key
        if account_id in kwargs:
            self.account_id = account_id
            
class OrderRequest(Account):
    def __init__(self, **kwargs)
        super().__init__(api_key=kwargs['api_key'], account_id=kwargs['account_id'])
        self.price              = kwargs['price']
        self.stop_loss          = kwargs['stop_loss']
        self.price_bound        = kwargs['price_bound']
        self.position_symbol    = kwargs['position_symbol']
        self.position_volume    = kwargs['position_volume']
    
    def send(self):
        url = f'/accounts/{self.account_id}/orders'
        headers = 
        {
            'Authorization'         :f'Bearer {self.api_key}',
            'Accept-Datetime-Format':'RFC3339',
            'Content-type'          :'application/json'
        }
        order_request_dict = 
        {
            'instrument'        : f'({position_symbol})',
            'units'             : f'({position_volume})',   # note that positive values are interpreted as a buy order and negative values are interpreted as a sell order
            'priceBound'        : f'({priceValue})',        # the worst price that the order will execute at
            'positionFill'      : f'(OPEN_ONLY)',
            'stopLossOnFill'    : {'price':f'{stop_loss}'}
        }
        data = json.dumps(order_dict)
        return requests.post(url,headers=headers,data=data)

def main():
    url = 'https://api-fxpractice.oanda.com/v3/accounts'
    api_key = '' 
    with open('api.key','r') as f:
        api_key = f.readlines()[0].replace('\n','')
    headers = {'Content-type':'application/json','Authorization':f'Bearer {api_key}'}
    response = requests.get(url,headers=headers)
    return response

if __name__ == "__main__":
    print(main().text)
