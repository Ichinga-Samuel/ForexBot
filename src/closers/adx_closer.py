from logging import getLogger

from aiomql import Positions, Symbol, TradePosition, OrderType

from .track_order import OpenOrder

logger = getLogger(__name__)


async def adx_closer(*, position: TradePosition, order: OpenOrder):
    try:
        print('Using Adx Closer')
        pos = Positions()
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
            position = await pos.position_get(ticket=position.ticket)
            if position is None:
                return
            if position.profit < 0:
                res = await pos.close_by(position)
                if res.retcode == 10009:
                    logger.warning(f"Exited trade {position.symbol}{position.ticket} with adx_closer")
                    position.config.state['order_tracker'].pop(position.ticket, None)
                else:
                    logger.error(f"Unable to close trade with adx_closer {res.comment}")
            else:
                adjust = cp_params['adjust']
                cp_params |= {'check_point': max(position.profit - adjust, adjust), 'close': True}
        else:
            logger.warning(f"ADX closer not triggered for {position.symbol}:{position.ticket}")
    except Exception as exe:
        logger.error(f'An error occurred in function adx_closer {exe}')
