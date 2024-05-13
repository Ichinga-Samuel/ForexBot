from logging import getLogger

from aiomql import Positions, Symbol, TradePosition, TimeFrame, Config, OrderType

logger = getLogger(__name__)


async def adx_closer(*, position: TradePosition, parameters: dict):
    try:
        pos = Positions()
        config = Config()
        fixed_closer = config.state['fixed_closer']
        hedges = config.state['hedges']
        sym = Symbol(name=position.symbol)
        await sym.init()
        exit_timeframe = parameters.get('exit_timeframe', TimeFrame.H1)
        ecc = parameters.get('ecc', 720)
        candles = await sym.copy_rates_from_pos(count=ecc, timeframe=exit_timeframe)
        adx = parameters.get('adx', 14)
        candles.ta.adx(append=True, length=adx)
        candles.rename(**{f"ADX_{adx}": "adx", f"DMP_{adx}": "dmp", f"DMN_{adx}": "dmn"})
        candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn)
        candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp)
        candles['pbn'] = candles.ta_lib.below(candles.dmp, candles.dmn)
        candles['nbp'] = candles.ta_lib.below(candles.dmn, candles.dmp)
        current = candles[-1]
        if position.type == OrderType.BUY and (current.nxp or current.pbn):
            close = True
        elif position.type == OrderType.SELL and (current.pxn or current.nbp):
            close = True
        else:
            close = False
        if close:
            positions = await pos.positions_get(ticket=position.ticket)
            position = positions[0] if positions else None
            if position is None:
                return
            if position.profit < 0:
                res = await pos.close_by(position)
                if res.retcode == 10009:
                    logger.warning(f"Exited trade {position.symbol}{position.ticket} with adx_closer")
                    if position.ticket in hedges:
                        rev = hedges[position.ticket]
                        hedges.pop(position.ticket)
                        positions = await pos.positions_get(ticket=rev)
                        rev_pos = positions[0] if positions else None
                        if rev_pos is not None:
                            if rev_pos.profit <= 0:
                                await pos.close_by(rev_pos)
                            else:
                                fixed_closer[rev.ticket] = {'cut_off': max(position.profit - 2, 0), 'close': True}
                else:
                    logger.error(f"Unable to close trade with adx_closer {res.comment}")
            else:
                close_adjust = fixed_closer[position.ticket].get('close_adjust', 2)
                fixed_closer[position.ticket] = {'cut_off': max(position.profit - close_adjust, 1), 'close': True}
    except Exception as exe:
        logger.error(f'An error occurred in function adx_closer {exe}')
