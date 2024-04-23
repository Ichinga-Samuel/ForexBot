from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame, Config

logger = getLogger(__name__)


async def stoch_closer(*, position: TradePosition, parameters: dict):
    try:
        pos = Positions()
        config = Config()
        fixed_closer = config.state.setdefault('fixed_closer', {})
        hedges = config.state.setdefault('hedges', {})
        order = config.state.setdefault('losing', {}).setdefault(position.ticket, {})
        sym = Symbol(name=position.symbol)
        await sym.init()
        exit_timeframe = parameters.get('exit_timeframe', TimeFrame.H1)
        exit_period = parameters.get('exit_period', 8)
        candles = await sym.copy_rates_from_pos(count=1000, timeframe=exit_timeframe)
        candles.ta.stoch(append=True)
        candles.rename(inplace=True, **{'STOCHk_14_3_3': 'stochk', 'STOCHd_14_3_3': 'stochd'})
        candles.ta.sma(close='stochd', length=exit_period, append=True)
        candles.rename(inplace=True, **{f'SMA_{exit_period}': 'sma'})
        
        if position.type == OrderType.BUY:
            sxs = candles.ta_lib.cross(candles.stochd, candles.sma, above=False)
        elif position.type == OrderType.SELL:
            sxs = candles.ta_lib.cross(candles.stochd, candles.sma, above=True)
        else:
            return
        if sxs.iloc[-1]:
            positions = await pos.positions_get(ticket=position.ticket)
            position = positions[0] if positions else None
            if position is None:
                return
            if position.profit < 0:
                res = await pos.close_by(position)
                if res.retcode == 10009:
                    logger.warning(f"Exited trade {position.symbol}{position.ticket} with stoch_closer")
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
                                fixed_closer[rev.ticket] = {'cut_off': max(position.profit - 1, 1), 'close': True}
                else:
                    logger.error(f"Unable to close trade with stoch_closer {res.comment}")
            else:
                fixed_closer[position.ticket] = {'cut_off': max(position.profit - 1, 1), 'close': True}
    except Exception as exe:
        logger.error(f'An error occurred in function stoch_closer {exe}')
