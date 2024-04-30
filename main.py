import requests
from environs import Env

if __name__ == '__main__':
    env = Env()
    env.read_env()

    starapi_token = env.str('API_TOKEN')

    url = 'http://localhost:1337/api/products'
    headers = {'Authorization': f'bearer {starapi_token}'}

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    print(response.text)
