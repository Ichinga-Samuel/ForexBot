import asyncio
from logging import getLogger
from datetime import datetime

from aiomql import Positions, TradePosition

logger = getLogger(__name__)


async def closer(*, time_elapsed=180, interval=60, **kwargs):
    pos = Positions()

    async def close(position: TradePosition):
        try:
            now = datetime.utcnow().timestamp()
            if now - float(position.comment) >= time_elapsed:
                await pos.close(price=position.price_current, ticket=position.ticket, order_type=position.type,
                                volume=position.volume, symbol=position.symbol)
        except Exception as ex:
            logger.warning(f'Unable to close position {ex}')

    while True:
        await asyncio.sleep(interval)
        try:
            positions = await pos.positions_get()
            orders = [close(position) for position in positions]
            await asyncio.gather(*[order for order in orders], return_exceptions=True)
        except Exception as exe:
            logger.warning(f'An error occurred in function closer {exe}')