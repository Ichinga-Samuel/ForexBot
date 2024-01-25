import asyncio
import logging

from aiomql import Config

from scripts.update_records import update_records

logging.basicConfig(level=logging.INFO)
c = Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral1')

asyncio.run(update_records())