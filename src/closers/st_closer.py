from logging import getLogger

from aiomql import Positions, TradePosition, Symbol, OrderType

logger = getLogger(__name__)


async def close_by_stoch(*, position: TradePosition, parameters: dict):
    try:
        pos = Positions()
        sym = Symbol(name=position.symbol)
        ot = position.type
        candles = await sym.copy_rates_from_pos(count=100, timeframe=parameters['etf'])
        candles.ta.stoch(append=True)
        candles.rename(**{'STOCHk_14_3_3': 'stochk', 'STOCHd_14_3_3': 'stochd'})
        current = candles[-1]
        if ot == OrderType.BUY and min(current.stochk, current.stochd) <= 30:
            await pos.close_by(position)
        elif ot == OrderType.SELL and max(current.stochk, current.stochd) >= 70:
            await pos.close_by(position)
    except Exception as exe:
        logger.warning(f'An error occurred in function close_by_stoch {exe}')
