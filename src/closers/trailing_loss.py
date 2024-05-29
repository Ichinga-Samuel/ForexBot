from logging import getLogger

from aiomql import Positions, Symbol, OrderType, Order, TradeAction

from ..utils.order_utils import calc_profit
from .track_order import OpenOrder

logger = getLogger(__name__)


async def trail_sl(*, order: OpenOrder):
    try:
        params = order.track_loss_params
        position = order.position
        trail_start = params['trail_start']
        previous_profit = params['previous_profit']
        trail_loss = trail_start * order.expected_loss
        trailing = params['trailing']
        if trailing and position.profit < min(previous_profit, trail_loss):
            await modify_sl(order=order)
    except Exception as exe:
        logger.error(f'Trailing stop loss for {order.position.symbol}:{order.position.ticket}'
                     f' failed due to {exe}{exe.__traceback__.tb_lineno}')


async def modify_sl(*, order: OpenOrder, extra: float = 0.0, tries: int = 4):
    try:
        position = order.position
        sym = Symbol(name=position.symbol)
        await sym.init()
        pos = Positions()
        position = await pos.position_get(ticket=position.ticket)
        params = order.track_loss_params
        trail = 1 - params['trail_start']
        full_points = abs(position.price_open - position.sl) / sym.point
        sl_points = full_points * trail
        # current_price = sym.tick.ask if position.type == OrderType.BUY else sym.tick.bid
        min_points = sym.trade_stops_level + sym.spread * (1 + extra)
        sl_points = max(sl_points*2, min_points)
        sl_value = round(sl_points * sym.point, sym.digits)
        if position.type == OrderType.BUY:
            sl = position.sl - sl_value
        else:
            sl = position.sl + sl_value
        trade_order = Order(position=position.ticket, sl=sl, tp=position.tp, action=TradeAction.SLTP)
        res = await trade_order.send()
        if res.retcode == 10009:
            params['previous_profit'] = position.profit
            req = res.request
            loss = calc_profit(sym=sym, open_price=position.price_open, close_price=req.sl, volume=position.volume,
                               order_type=position.type)
            order.expected_loss = loss
            logger.warning(f"Trailing stop loss for {position.symbol}:{position.ticket} successful. New loss is {loss}")
        elif res.retcode == 10016 and tries > 0:
            await modify_sl(order=order, extra=extra + 0.01, tries=tries - 1)
        else:
            logger.error(f"Trailing stop loss failed due to {res.comment} for {position.symbol}:{position.ticket}")
    except Exception as exe:
        logger.error(f'Trailing stop loss failed due to'
                     f' {exe}@{exe.__traceback__.tb_lineno} for {order.position.symbol}:{order.ticket}')
