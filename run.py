import asyncio
from aiomql import Config

from scripts.closer import place_multiple_random_orders
Config(config_dir='configs', filename='deriv_demo.json', reload=True, record_trades=False)
asyncio.run(place_multiple_random_orders())