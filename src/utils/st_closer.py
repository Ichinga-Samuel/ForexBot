import asyncio
from logging import getLogger

from aiomql import Positions, TradePosition, Symbol, TimeFrame, OrderType, Config

from .sleep import sleep

logger = getLogger(__name__)


async def st_closer(*, timeframe: TimeFrame = TimeFrame.M15, **kwargs):
    pos = Positions()

    async def close_by_stoch(open_pos: TradePosition):
        sym = Symbol(name=open_pos.symbol)
        ot = open_pos.type
        candles = await sym.copy_rates_from_pos(count=100, timeframe=timeframe)
        candles.ta.stoch(append=True)
        candles.rename(**{'STOCHk_14_3_3': 'stochk', 'STOCHd_14_3_3': 'stochd'})
        current = candles[-1]
        if ot == OrderType.BUY and min(current.stochk, current.stochd) <= 30:
            await pos.close_by(open_pos)
        elif ot == OrderType.SELL and max(current.stochk, current.stochd) >= 70:
            await pos.close_by(open_pos)

    while True:
        await sleep(timeframe.time)
        try:
            config = Config()
            data = config.state.get('mfi', {})
            positions = await pos.positions_get()
            positions = [position for position in positions if position.ticket in data]
            orders = [close_by_stoch(position) for position in positions]
            await asyncio.gather(*[order for order in orders], return_exceptions=True)
        except Exception as exe:
            logger.warning(f'An error occurred in function closer {exe}')