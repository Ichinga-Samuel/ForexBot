from logging import getLogger

from aiomql import Positions, Symbol, OrderType

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
        candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn, asint=False)
        candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp, asint=False)
        current = candles[-1]

        if position.type == OrderType.BUY and current.nxp:
            ...
        elif position.type == OrderType.SELL and current.pxn:
            ...
        else:
            return

        position = await pos.position_get(ticket=order.ticket)
        assert position is not None, 'Position not found'

        if position.profit < 0:
            res = await pos.close_by(position)
            if res.retcode == 10009:
                logger.info(f"Exited trade {position.symbol}{position.ticket} with adx_closer")
                order.config.state['tracked_orders'].pop(order.ticket, None)
            else:
                logger.error(f"Unable to close trade with adx_closer {res.comment}")
        else:
            adjust = cp_params['exit_adjust']
            check_point = position.profit * adjust
            cp_params |= {'check_point': check_point, 'close': True, 'use_check_points': True}
    except Exception as exe:
        logger.error(f"An error occurred in function adx_closer {exe}")
