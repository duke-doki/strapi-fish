import pprint

import requests
from environs import Env
from io import BytesIO


env = Env()
env.read_env()
starapi_token = env.str('API_TOKEN')


def fetch_products():
    url = 'http://localhost:1337/api/products'
    headers = {'Authorization': f'bearer {starapi_token}'}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    products = response.json()
    return products


def get_product_by_id(product_id):
    url = f'http://localhost:1337/api/products/{product_id}'
    headers = {'Authorization': f'bearer {starapi_token}'}
    params = {'populate': 'Picture'}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    product = response.json()
    image_url = product['data']['attributes']['Picture']['data'][0]['attributes']['url']
    image_url = f'http://localhost:1337{image_url}'
    image = download_image(image_url, product_id)
    return product, image


def download_image(url, pic_id):
    headers = {'Authorization': f'bearer {starapi_token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    image_data = BytesIO(response.content)
    return image_data


if __name__ == '__main__':
    pprint.pprint(get_product_by_id(2))
