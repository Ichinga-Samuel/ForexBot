from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame

from .trailing_stop import modify_order

logger = getLogger(__name__)


async def ema_rsi_closer(*, position: TradePosition, parameters: dict):
    try:
        positions = Positions()
        sym = Symbol(name=position.symbol)
        await sym.init()
        tf = parameters.get('etf', parameters.get('etf', TimeFrame.H1))
        tcc = 100

        first_ema = parameters.get('first_ema', 8)
        second_ema = parameters.get('second_ema', 13)
        # rsi_level = parameters['rsi_level']
        order_type = position.type
        candles = await sym.copy_rates_from_pos(count=tcc, timeframe=tf)
        candles.ta.ema(length=first_ema, append=True)
        candles.ta.ema(length=second_ema, append=True)
        candles.ta.rsi(append=True)
        candles.rename(**{f"EMA_{first_ema}": "first", f"EMA_{second_ema}": "second",
                          "RSI_14": "rsi"})
        if order_type == OrderType.BUY:
            fxs = candles.ta_lib.cross(candles.first, candles.second, above=False)
            if any(fxs.iloc[-2:]):
                position = await positions.positions_get(ticket=position.ticket)
                position = position[0]
                if position.profit > 0:
                    await modify_order(pos=position, symbol=sym)
                else:
                    res = await positions.close_by(position)
                    if res.retcode == 10009:
                        logger.warning(f"Closed trade {position.ticket} with ema_rsi_closer")
                    else:
                        logger.error(f"Unable to close trade in ema_rsi_closer {res.comment}")
        elif order_type == OrderType.SELL:
            fxs = candles.ta_lib.cross(candles.first, candles.second, above=True)
            if any(fxs.iloc[-2:]):
                position = await positions.positions_get(ticket=position.ticket)
                position = position[0]
                if position.profit > 0:
                    await modify_order(pos=position, symbol=sym)
                else:
                    res = await positions.close_by(position)
                    if res.retcode == 10009:
                        logger.info(f"Closed trade {position.ticket} with ema_rsi_closer")
                    else:
                        logger.error(f"Unable to close trade in ema_rsi_closer {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function ema_rsi_closer {exe}')
