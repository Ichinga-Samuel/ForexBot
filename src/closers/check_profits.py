from logging import getLogger

from aiomql import Positions, TradePosition

from .track_order import OpenOrder

logger = getLogger(__name__)


async def fixed_check_profit(*, position: TradePosition, order: OpenOrder):
    try:
        orders = position.config.state['order_tracker']
        check_profit_params = order.check_profit_params
        check_points = check_profit_params['check_points']
        pos = Positions()
        position = await pos.position_get(ticket=position.ticket)
        if check_profit_params['close'] and position.profit < check_profit_params['check_point']:
            res = await pos.close_by(position)
            if res.retcode == 10009:
                logger.info(f"Closed trade {position.ticket} with fixed_closer")
                orders.pop(position.ticket) if position.ticket in orders else ...
            else:
                logger.error(f"Unable to close order in check_profit due to {res.comment}")
        keys = check_points.keys()
        if len(keys) and check_profit_params['use_check_points']:
            keys = sorted(keys)
            check_point = keys[0]
            if position.profit >= check_point:
                check_profit_params |= {'close': True, 'check_point': check_point}
                check_points.pop(check_point) if check_point in check_points else ...
    except Exception as exe:
        logger.error(f'An error occurred in function fixed_check_profit {exe}')
