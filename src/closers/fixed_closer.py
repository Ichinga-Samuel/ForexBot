from logging import getLogger

from aiomql import Positions, Symbol, Config, TradePosition

logger = getLogger(__name__)


async def fixed_closer(*, position: TradePosition):
    try:
        config = Config()
        cap = config.state.get('profits', {}).get(position.ticket, {}).get('cap', 3)
        positions = Positions()
        position = await positions.positions_get(ticket=position.ticket)
        position = position[0]
        if position.profit > cap:
            res = await positions.close_by(position)
            if res.retcode == 10009:
                logger.warning(f"Closed trade {position.ticket} with fixed_closer")
            else:
                logger.error(f"Unable to close trade in fixed_closer {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function fixed_closer {exe}')
