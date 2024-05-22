import asyncio
from logging import getLogger

from aiomql import Positions

from ..utils.sleep import sleep
from .track_order import TrackOrder

logger = getLogger(__name__)


async def monitor(*, tf: int = 31):
    print('Trade Monitoring started')
    pos = Positions()
    config = pos.mt5.config
    while True:
        try:
            tasks = []
            positions = await pos.positions_get()
            track = getattr(config, 'track_orders', True)
            if track:
                tracked = config.state['order_tracker']
                open_trades = [TrackOrder(position=position) for position in positions if position.ticket in tracked]
                closers = [trade.track() for trade in open_trades]
                tasks.extend(closers)
            await asyncio.gather(*tasks, return_exceptions=True)
            await sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function monitor {exe}')
            await sleep(tf)
