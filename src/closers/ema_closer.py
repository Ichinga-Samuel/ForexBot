from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame, Config

logger = getLogger(__name__)


async def ema_closer(*, position: TradePosition, parameters: dict):
    try:
        pos = Positions()
        config = Config()
        fixed_closer = config.state['fixed_closer']
        hedges = config.state['hedges']
        sym = Symbol(name=position.symbol)
        await sym.init()
        exit_timeframe = parameters.get('exit_timeframe', TimeFrame.M15)
        exit_ema = parameters.get('exit_ema', 5)
        candles = await sym.copy_rates_from_pos(count=1000, timeframe=exit_timeframe)
        candles.ta.ema(length=exit_ema, append=True)
        candles.rename(**{f"EMA_{exit_ema}": "ema"})

        if position.type == OrderType.BUY:
            cxe = candles.ta_lib.cross(candles.close, candles.ema, above=False)
        elif position.type == OrderType.SELL:
            cxe = candles.ta_lib.cross(candles.close, candles.ema, above=True)
        else:
            return
        if cxe.iloc[-1]:
            positions = await pos.positions_get(ticket=position.ticket)
            position = positions[0] if positions else None
            if not position:
                return
            if position.profit <= 0:
                res = await pos.close_by(position)
                if res.retcode == 10009:
                    logger.warning(f"Exited trade {position.symbol}{position.ticket} with ema_closer")
                    if position.ticket in hedges:
                        rev = hedges[position.ticket]
                        hedges.pop(position.ticket)
                        positions = await pos.positions_get(ticket=rev)
                        rev_pos = positions[0] if positions else None
                        if rev_pos:
                            if rev_pos.profit <= 0:
                                await pos.close_by(rev_pos)
                                logger.warning(f"Closed hedge {rev} for {position.ticket}")
                            fixed_closer[rev.ticket] = {'cut_off': max(position.profit - 1, 1), 'close': True}
                else:
                    logger.error(f"Unable to close trade in ema_closer {res.comment}")
            else:
                fixed_closer[position.ticket] = {'cut_off': max(position.profit - 0.5, 0.5), 'close': True}
    except Exception as exe:
        logger.error(f'An error occurred in function ema_closer {exe}')
