from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame

logger = getLogger(__name__)


async def ema_closer(*, position: TradePosition, parameters: dict):
    try:
        positions = Positions()
        sym = Symbol(name=position.symbol)
        await sym.init()
        tf = TimeFrame.M15
        cc = 1000
        order_type = position.type
        candles = await sym.copy_rates_from_pos(count=cc, timeframe=tf)
        fast_ema, slow_ema = 8, 13
        candles.ta.ema(length=fast_ema, append=True)
        candles.ta.ema(length=slow_ema, append=True)
        candles.rename(**{f"EMA_{fast_ema}": "fast_ema", f"EMA_{slow_ema}": "slow_ema"})
        if order_type == OrderType.BUY:
            fxs = candles.ta_lib.cross(candles.fast_ema, candles.slow_ema, above=False)
            if any(fxs.iloc[-2:]):
                position = await positions.positions_get(ticket=position.ticket)
                position = position[0]
                if position.profit < 0:
                    res = await positions.close_by(position)
                    if res.retcode == 10009:
                        logger.warning(f"Closed trade {position.ticket} with ema_closer")
                    else:
                        logger.error(f"Unable to close trade in ema_closer {res.comment}")
        elif order_type == OrderType.SELL:
            fxs = candles.ta_lib.cross(candles.fast_ema, candles.slow_ema, above=True)
            if any(fxs.iloc[-2:]):
                position = await positions.positions_get(ticket=position.ticket)
                position = position[0]
                if position.profit < 0:
                    res = await positions.close_by(position)
                    if res.retcode == 10009:
                        logger.warning(f"Closed trade {position.ticket} with ema_closer")
                    else:
                        logger.error(f"Unable to close trade in ema_closer {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function ema_closer {exe}')
