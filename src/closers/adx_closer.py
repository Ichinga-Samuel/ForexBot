from logging import getLogger

from aiomql import Positions, Symbol, TradePosition, OrderType

from .track_order import OpenOrder

logger = getLogger(__name__)


async def adx_closer(*, order: OpenOrder):
    try:
        pos = Positions()
        position = order.position
        sym = Symbol(name=position.symbol)
        await sym.init()
        parameters = order.strategy_parameters
        cp_params = order.check_profit_params
        exit_timeframe = parameters['exit_timeframe']
        cc = parameters['excc']
        candles = await sym.copy_rates_from_pos(count=cc, timeframe=exit_timeframe)
        adx = parameters['adx']
        candles.ta.adx(append=True, length=adx)
        candles.rename(**{f"ADX_{adx}": "adx", f"DMP_{adx}": "dmp", f"DMN_{adx}": "dmn"})
        candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn)
        candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp)
        current = candles[-1]

        if position.type == OrderType.BUY and current.nxp:
            close = True
        elif position.type == OrderType.SELL and current.pxn:
            close = True
        else:
            close = False

        if close:
            position = await pos.position_get(ticket=order.ticket)
            if position is None:
                return

            if position.profit < 0:
                res = await pos.close_by(position)
                if res.retcode == 10009:
                    logger.info(f"Exited trade {position.symbol}{position.ticket} with adx_closer")
                    order.config.state['order_tracker'].pop(order.ticket, None)
                else:
                    logger.error(f"Unable to close trade with adx_closer {res.comment}")

                if order.hedged:
                    rev_order = order.hedged_order
                    rev_pos = await pos.position_get(ticket=rev_order.ticket)
                    if rev_pos is None:
                        return

                    if rev_pos.profit < 0:
                        res = await pos.close_by(rev_pos)
                        if res.retcode == 10009:
                            logger.info(f"Closed hedge {rev_pos.symbol}:{rev_pos.ticket}")
                            order.config.state['order_tracker'].pop(rev_order.ticket, None)
                        else:
                            logger.error(f"Unable to close hedge {rev_pos.symbol}:{rev_pos.ticket}")
                    else:
                        rev_order.check_profit = True
                        rev_order.track_profit = True
                        rev_order.track_profit_params |= {'start_trailing': True}
                        adjust = cp_params['hedge_adjust']
                        check_point = rev_pos.profit * adjust
                        cp_params |= {'close': True, 'check_point': check_point, 'use_check_points': True}

            else:
                adjust = cp_params['exit_adjust']
                check_point = position.profit * adjust
                cp_params |= {'check_point': check_point, 'close': True, 'use_check_points': True}
    except Exception as exe:
        logger.error(f"An error occurred in function adx_closer {exe}")
