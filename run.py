import asyncio
from aiomql import Config

from scripts.update_records import update_records
Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1')
asyncio.run(update_records())