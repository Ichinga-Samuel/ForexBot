from logging import getLogger

from aiomql import Positions

from .track_order import OpenOrder

logger = getLogger(__name__)


async def fixed_check_profit(*, order: OpenOrder):
    try:
        check_profit_params = order.check_profit_params
        check_points = check_profit_params['check_points']
        pos = Positions()
        position = await pos.position_get(ticket=order.ticket)
        current_check_point = check_profit_params['check_point']
        if check_profit_params['close'] and position.profit < current_check_point:
            res = await pos.close_by(position)
            if res.retcode == 10009:
                logger.info(f"Closed trade {position.ticket}:{position.symbol}@{position.profit=} at checkpoint")
                order.config.state['tracked_orders'].pop(position.ticket, None)
                return
            else:
                logger.error(f"Unable to close order in check_profit due to {res.comment}")

        if check_profit_params['use_check_points'] and len(keys := sorted(check_points.keys())):
            key = keys[0]
            check_point = check_points[key]
            if position.profit >= key:
                if check_point > current_check_point:
                    check_profit_params |= {'close': True, 'check_point': check_point}
                check_points.pop(key, None)
                logger.info(
                    f"Check point set for {position.symbol}:{position.ticket}@{check_point} using fixed_check_profit")
    except Exception as exe:
        logger.error(f'An error occurred in function fixed_check_profit {exe}@{exe.__traceback__.tb_lineno}')


async def ratio_check_profit(*, order: OpenOrder):
    try:
        check_profit_params = order.check_profit_params
        check_points = check_profit_params['check_points']
        pos = Positions()
        position = await pos.position_get(ticket=order.ticket)
        current_check_point = check_profit_params['check_point']
        if check_profit_params['close'] and position.profit < current_check_point:
            res = await pos.close_by(position)
            if res.retcode == 10009:
                logger.info(f"Closed trade {position.symbol}:{position.ticket}@{position.profit} at checkpoint")
                order.config.state['tracked_orders'].pop(position.ticket, None)
                return
            else:
                logger.error(f"Unable to close order in check_profit due to {res.comment}")

        if check_profit_params['use_check_points'] and len(keys := sorted(check_points.keys())):
            expected_profit = order.expected_profit
            key = keys[0]
            check_point = check_points[key] * expected_profit
            if position.profit >= key * expected_profit:
                if check_point > current_check_point:
                    check_profit_params |= {'close': True, 'check_point': check_point}
                check_points.pop(key, None)
                logger.info(f"Check point set for {position.symbol}:{position.ticket}@{check_point}"
                             f"using ratio_check_profit")
    except Exception as exe:
        logger.error(f'An error occurred in function ratio_check_profit {exe}@{exe.__traceback__.tb_lineno}')
