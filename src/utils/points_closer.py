import asyncio
from logging import getLogger

from aiomql import Positions, TradePosition, Symbol, TimeFrame, OrderType, Config

from .sleep import sleep

logger = getLogger(__name__)


async def points_closer(*, timeframe: TimeFrame = TimeFrame.M2):
    pos = Positions()

    async def close_at_sl(*, open_pos: TradePosition, sl: float, tp: float):
        sym = Symbol(name=open_pos.symbol)
        tick = await sym.info_tick()
        if open_pos.type == OrderType.BUY and (tick.bid <= sl or tick.bid >= tp):
            await pos.close_by(open_pos)
        elif open_pos.type == OrderType.SELL and (tick.ask >= sl or tick.ask <= tp):
            await pos.close_by(open_pos)
        else:
            return

    while True:
        await sleep(timeframe.time)
        try:
            config = Config()
            data = config.state.get('c_trader', {})
            positions = await pos.positions_get()
            positions = [(position, data['close_sl'], data['close_tp']) for position in positions if position.ticket in data]
            orders = [close_at_sl(open_pos=position[0], sl=position[1], tp=position[2]) for position in positions]
            await asyncio.gather(*[order for order in orders], return_exceptions=True)
        except Exception as exe:
            logger.error(f'An error occurred in function closer {exe}')