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
                tracked_orders = config.state['tracked_orders']
                open_orders = {}
                for position in positions:
                    if (ticket := position.ticket) in tracked_orders:
                        open_order = tracked_orders[ticket]
                        open_order.position = position
                        tasks.append(TrackOrder(order=open_order).track())
                        open_orders[ticket] = open_order
                config.state['tracked_orders'] = open_orders

            await asyncio.gather(*tasks, return_exceptions=True)
            await sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function monitor {exe}')
            await sleep(tf)
