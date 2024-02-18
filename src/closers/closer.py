import asyncio
from logging import getLogger

from aiomql import Positions, TimeFrame, Config, TradePosition

from ..utils.sleep import sleep

logger = getLogger(__name__)


class OpenTrade:
    def __init__(self, *, position: TradePosition, parameters: dict):
        self.position = position
        self.parameters = parameters

    async def close(self):
        try:
            trade_closer = self.parameters.get('closer')
            await trade_closer(position=self.position, parameters=self.parameters)
        except Exception as exe:
            logger.error(f'An error occurred in function OpenTrade.close {exe}')


async def closer(*, tf: TimeFrame = TimeFrame.M5, key: str = 'trades'):
    print('Closer started')
    await sleep(tf.time)
    conf = Config()
    pos = Positions()
    while True:
        try:
            data = conf.state.get(key, {})
            positions = await pos.positions_get()
            open_trades = [OpenTrade(position=p, parameters=data[p.ticket]) for p in positions if p.ticket in data]
            await asyncio.gather(*[trade.close() for trade in open_trades], return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function closer {exe}')
            await sleep(tf.time)
