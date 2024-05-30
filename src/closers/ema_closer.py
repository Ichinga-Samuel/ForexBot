from logging import getLogger

from aiomql import Positions, Symbol, OrderType

from .track_order import OpenOrder

logger = getLogger(__name__)


async def ema_closer(*, order: OpenOrder):
    try:
        pos = Positions()
        position = order.position
        parameters = order.strategy_parameters

        sym = Symbol(name=position.symbol)
        await sym.init()
        exit_timeframe = parameters['exit_timeframe']
        exit_ema = parameters['exit_ema']
        candles = await sym.copy_rates_from_pos(count=720, timeframe=exit_timeframe)
        candles.ta.ema(length=exit_ema, append=True)
        candles.rename(**{f"EMA_{exit_ema}": "ema"})
        candles['cbe'] = candles.ta_lib.cross(candles.close, candles.ema, above=False, asint=False)
        candles['cae'] = candles.ta_lib.cross(candles.close, candles.ema, asint=False)
        current = candles[-1]
        if position.type == OrderType.BUY and current.cbe:
            ...
        elif position.type == OrderType.SELL and current.cae:
            ...
        else:
            return

        position = await pos.position_get(ticket=position.ticket)
        assert position is not None, 'Position not found'

        if position.profit <= 0:
            res = await pos.close_by(position)
            if res.retcode == 10009:
                order.config.state['tracked_orders'].pop(order.ticket, None)
                logger.info(f"Exited trade {position.symbol}:{position.ticket} with ema_closer")
            else:
                logger.error(f"Unable to close trade in ema_closer {res.comment}")
        else:
            adjust = order.check_profit_params['exit_adjust']
            check_point = position.profit * adjust
            order.check_profit_params |= {'close': True, 'check_point': check_point, 'use_check_point': True}
    except Exception as exe:
        logger.error(f'An error occurred in function ema_closer {exe}@{exe.__traceback__.tb_lineno}')
