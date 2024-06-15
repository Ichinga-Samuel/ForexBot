from logging import getLogger

from aiomql import Positions, Symbol, OrderType

from .hedge import hedge_position
from .track_order import OpenOrder

logger = getLogger(__name__)


async def adx_closer(*, order: OpenOrder):
    try:
        pos = Positions()
        position = order.position
        sym = Symbol(name=position.symbol)
        await sym.init()
        parameters = order.strategy_parameters
        exit_timeframe = parameters['exit_timeframe']
        cc = parameters['excc']
        candles = await sym.copy_rates_from_pos(count=cc, timeframe=exit_timeframe)
        adx = parameters['exit_adx']
        candles.ta.adx(append=True, length=adx, mamode='ema')
        candles.rename(**{f"ADX_{adx}": "adx", f"DMP_{adx}": "dmp", f"DMN_{adx}": "dmn"})
        candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn, asint=False)
        candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp, asint=False)
        current = candles[-1]

        if position.type == OrderType.BUY and (current.nxp or current.adx < 25):
            ...
        elif position.type == OrderType.SELL and (current.pxn or current.adx < 25):
            ...
        else:
            return

        position = await pos.position_get(ticket=order.ticket)
        if position is None:
            return

        if position.profit < 0:
            if order.hedge_on_exit and order.hedged is False:
                await hedge_position(order=order)
            res = await pos.close_by(position)
            if res.retcode == 10009:
                logger.debug(f"Exited trade {position.symbol}{position.ticket} with adx_closer")
                order.config.state['tracked_orders'].pop(order.ticket, None)
            else:
                logger.error(f"Unable to close trade with adx_closer {res.comment}")
        else:
            cp_params = order.check_profit_params
            adjust = cp_params['exit_adjust']
            check_point = position.profit * adjust
            trail_start = position.profit / order.expected_profit
            order.track_profit_params |= {'trail_start': trail_start}
            cp_params |= {'check_point': check_point, 'close': True, 'use_check_points': True}
            order.check_profit_params = cp_params
            order.use_exit_signal = False
            logger.debug(f"Check point set for {position.symbol}:{position.ticket}@{check_point} using adx_closer")
    except Exception as exe:
        logger.error(f"An error occurred in function adx_closer {exe}")
