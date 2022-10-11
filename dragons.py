import requests
url = 'https://api-fxpractice.oanda.com/v3/accounts'
api_key = '' 
with open('api.key','r') as f:
    api_key = f.readlines()[0].replace('\n','')
print(api_key)
headers = {'Content-Type':'application/json','Authorization':f'Bearer {api_key}'}
response = requests.get(url,headers)
print(response.text)
