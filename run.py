import asyncio
from aiomql import Config

from scripts.update_records import update_records
from scripts.closer import place_multiple_random_orders as red
con = Config(config_dir='configs', filename='derived_scalper.json', reload=True, record_trade=False)
# Config(reload=True, records_dir='records/deriv/', trade_record_mode='json')
asyncio.run(red())
