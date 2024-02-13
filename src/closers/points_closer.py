from logging import getLogger

from aiomql import Positions, TradePosition, Symbol, OrderType

logger = getLogger(__name__)


async def close_at_sl(*, position: TradePosition, parameters: dict):
    try:
        pos = Positions()
        sym = Symbol(name=position.symbol)
        sl = parameters['close_sl']
        tp = parameters['close_tp']
        tick = await sym.info_tick()
        if position.type == OrderType.BUY and (tick.bid <= sl or tick.bid >= tp):
            await pos.close_by(position)
        elif position.type == OrderType.SELL and (tick.ask >= sl or tick.ask <= tp):
            await pos.close_by(position)
        else:
            return
    except Exception as exe:
        logger.warning(f'An error occurred in function close_at_sl {exe}')
