from logging import getLogger

from aiomql import Positions, Config, TradePosition

logger = getLogger(__name__)


async def fixed_closer(*, position: TradePosition):
    try:
        config = Config()
        fixed = config.state.setdefault('fixed_closer', {})
        pos = Positions()
        ticket = position.ticket
        positions = await pos.positions_get(ticket=ticket)
        position = positions[0] if positions else None
        if not position:
            fixed.pop(ticket) if ticket in fixed else ...
            return
        order = fixed[position.ticket]
        if order.get('close', False) and position.profit <= order['cut_off']:
            res = await pos.close_by(position)
            if res.retcode == 10009:
                fixed.pop(position.ticket) if position.ticket in fixed else ...
                logger.warning(f"Closed trade {position.ticket} with fixed_closer")
            else:
                logger.error(f"Unable to close trade in fixed_closer {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function fixed_closer {exe}')
