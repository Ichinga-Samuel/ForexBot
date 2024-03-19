from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame

logger = getLogger(__name__)


async def ema_rsi_closer(*, position: TradePosition, parameters: dict):
    try:
        pos = Positions()
        sym = Symbol(name=position.symbol)
        await sym.init()
        tf = TimeFrame.H1
        cc = 1000
        first_ema = parameters.get('first_ema', 13)
        second_ema = parameters.get('second_ema', 21)
        order_type = position.type
        candles = await sym.copy_rates_from_pos(count=cc, timeframe=tf)
        candles.ta.ema(length=first_ema, append=True)
        candles.ta.ema(length=second_ema, append=True)
        candles.ta.rsi(append=True)
        candles.rename(**{f"EMA_{first_ema}": "first", f"EMA_{second_ema}": "second"})
        if order_type == OrderType.BUY:
            fxs = candles.ta_lib.cross(candles.first, candles.second, above=False)
            if any(fxs.iloc[-2:]):
                positions = await pos.positions_get(ticket=position.ticket)
                position = positions[0]
                if position.profit < 0:
                    res = await pos.close_by(position)
                    if res.retcode == 10009:
                        logger.warning(f"Closed trade {position.ticket} with ema_rsi_closer")
                    else:
                        logger.error(f"Unable to close trade in ema_rsi_closer {res.comment}")
        elif order_type == OrderType.SELL:
            fxs = candles.ta_lib.cross(candles.first, candles.second, above=True)
            if any(fxs.iloc[-2:]):
                positions = await pos.positions_get(ticket=position.ticket)
                position = positions[0]
                if position.profit < 0:
                    res = await pos.close_by(position)
                    if res.retcode == 10009:
                        logger.info(f"Closed trade {position.ticket} with ema_rsi_closer")
                    else:
                        logger.error(f"Unable to close trade in ema_rsi_closer {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function ema_rsi_closer {exe}')
