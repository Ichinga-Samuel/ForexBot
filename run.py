import asyncio
from aiomql import Config

# from scripts.update_records import update_records
from scripts.closer import place_multiple_random_orders as red
con = Config(config_dir='configs', filename='deriv1.json', reload=True, record_trade=False)
asyncio.run(red())
