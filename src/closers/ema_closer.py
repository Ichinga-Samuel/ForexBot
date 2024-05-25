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
        candles = await sym.copy_rates_from_pos(count=1000, timeframe=exit_timeframe)
        candles.ta.ema(length=exit_ema, append=True)
        candles.rename(**{f"EMA_{exit_ema}": "ema"})

        if position.type == OrderType.BUY:
            candles['cxe'] = candles.ta_lib.cross(candles.close, candles.ema, above=False)
        elif position.type == OrderType.SELL:
            candles['cxe'] = candles.ta_lib.cross(candles.close, candles.ema, above=True)
        else:
            return
        current = candles[-1]
        if current.cxe:
            position = await pos.position_get(ticket=position.ticket)
            if not position:
                return
            if position.profit <= 0:
                res = await pos.close_by(position)
                if res.retcode == 10009:
                    order.config.state['order_tracker'].pop(order.ticket, None)
                    logger.info(f"Exited trade {position.symbol}:{position.ticket} with ema_closer")
                    if order.hedged:
                        rev_order = order.hedged_order
                        rev_pos = await pos.position_get(ticket=rev_order.ticket)
                        if rev_pos:
                            if rev_pos.profit <= 0:
                                res = await pos.close_by(rev_pos)
                                if res.retcode == 10009:
                                    order.config.state['order_tracker'].pop(rev_order.ticket, None)
                                    logger.info(f"Closed hedge {rev_pos.symbol}:{position.ticket}")
                                else:
                                    logger.error(f"Unable to close hedge {rev_pos.symbol}:{position.ticket}")
                            else:
                                rev_order.check_profit = True
                                rev_order.track_profit = True
                                rev_order.track_profit_params |= {'start_trailing': True}
                                adjust = rev_order.check_profit_params['hedge_adjust']
                                check_point = rev_pos.profit * adjust
                                rev_order.check_profit_params |= {'close': True, 'check_point': check_point,
                                                                  'use_check_points': True}
                else:
                    logger.error(f"Unable to close trade in ema_closer {res.comment}")
            else:
                adjust = order.check_profit_params['exit_adjust']
                check_point = position.profit * adjust
                order.check_profit_params |= {'close': True, 'check_point': check_point, 'use_check_point': True}
    except Exception as exe:
        logger.error(f'An error occurred in function ema_closer {exe}')
