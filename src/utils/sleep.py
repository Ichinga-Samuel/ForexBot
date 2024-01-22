import asyncio
from time import time


async def sleep(secs: float):
    """Sleep for the needed amount of seconds in between requests to the terminal.
    computes the accurate amount of time needed to sleep ensuring that the next request is made at the start of
    a new bar and making cooperative multitasking possible.

    Args:
        secs (float): The time in seconds. Usually the timeframe you are trading on.
    """
    mod = time() % secs
    secs = secs - mod if mod != 0 else mod
    await asyncio.sleep(secs)