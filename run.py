import asyncio
import logging

from scripts.closer import close_all

asyncio.run(close_all())