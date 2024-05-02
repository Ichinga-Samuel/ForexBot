from logging import getLogger

from aiomql import Positions, Symbol, TradePosition, TimeFrame, Config

logger = getLogger(__name__)


async def adx_closer(*, position: TradePosition, parameters: dict):
    try:
        pos = Positions()
        config = Config()
        fixed_closer = config.state.setdefault('fixed_closer', {})
        hedges = config.state.setdefault('hedges', {})
        order = config.state.setdefault('losing', {}).setdefault(position.ticket, {})
        sym = Symbol(name=position.symbol)
        await sym.init()
        exit_timeframe = parameters.get('exit_timeframe', TimeFrame.H4)
        exit_period = parameters.get('exit_period', 13)
        candles = await sym.copy_rates_from_pos(count=720, timeframe=exit_timeframe)
        candles.ta.adx(append=True, lensig=50)
        candles.rename(**{'ADX_50': 'adx'})
        candles.ta.sma(close='adx', length=exit_period, append=True)
        candles.ta.rsi(close='SMA_13', length=5, append=True)
        candles.rename(**{f'SMA_13': 'sma', 'RSI_5': 'rsi'})
        candles['sxs'] = candles.ta_lib.cross(candles.adx, candles.sma, above=False)
        candles['sbx'] = candles.ta_lib.below(candles.adx, candles.sma)
        current = candles[-1]
        if current.sxs or current.sbx or current.rsi < 70:
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
                            hedge_point = order.get('hedge_point', 0)
                            if rev_pos.profit <= hedge_point:
                                await pos.close_by(rev_pos)
                                logger.warning(f"Closed hedge {rev} for {position.ticket}")
                            elif hedge_point < rev_pos.profit <= 0:
                                fixed_closer[rev.ticket] = {'cut_off': hedge_point, 'close': True}
                            elif rev_pos.profit > 0:
                                fixed_closer[rev.ticket] = {'cut_off': max(position.profit - 1, 0), 'close': True}
                else:
                    logger.error(f"Unable to close trade with adx_closer {res.comment}")
            else:
                fixed_closer[position.ticket] = {'cut_off': max(position.profit - 1, 1), 'close': True}
    except Exception as exe:
        logger.error(f'An error occurred in function adx_closer {exe}')
