from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame

logger = getLogger(__name__)


async def ema_closer(*, position: TradePosition, parameters: dict):
    try:
        positions = Positions()
        sym = Symbol(name=position.symbol)
        await sym.init()
        tf = parameters.get('etf', parameters.get('ttf', TimeFrame.M15))
        tcc = parameters['tcc']
        order_type = position.type
        candles = await sym.copy_rates_from_pos(count=tcc, timeframe=tf)
        fast_ema, slow_ema = parameters['fast_ema'], parameters['slow_ema']
        candles.ta.ema(length=fast_ema, append=True)
        candles.ta.ema(length=slow_ema, append=True)
        candles.rename(**{f"EMA_{fast_ema}": "fast_ema", f"EMA_{slow_ema}": "slow_ema"})
        if order_type == OrderType.BUY:
            fxs = candles.ta_lib.cross(candles.fast_ema, candles.slow_ema, above=False)
            if any(fxs[-2:]):
                await positions.close_by(position)
                logger.info(f"Closed trade {position.ticket}")
        elif order_type == OrderType.SELL:
            fxs = candles.ta_lib.cross(candles.fast_ema, candles.slow_ema, above=True)
            if any(fxs[-2:]):
                await positions.close_by(position)
                logger.info(f"Closed trade {position.ticket}")
    except Exception as exe:
        logger.error(f'An error occurred in function ema_closer {exe}')
