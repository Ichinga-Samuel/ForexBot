from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, OrderSendResult

from ..utils.order_utils import calc_profit
from .track_order import OpenOrder
logger = getLogger(__name__)


async def trail_tp(*, order: OpenOrder):
    try:
        position = order.position
        params = order.track_profit_params
        start_trailing = params['start_trailing']
        trail_start = params['trail_start'] * order.expected_profit
        previous_profit = params['previous_profit']
        if start_trailing and (position.profit >= max(trail_start, previous_profit)):
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(order=order)
    except Exception as exe:
        logger.error(f"{exe}@{exe.__traceback__.tb_lineno} in modify_stop for {order.position.symbol}:{order.ticket}")


async def modify_stops(*, order: OpenOrder, extra: float = 0.0, tries: int = 4):
    try:
        pos = Positions()
        position = await pos.position_get(ticket=order.ticket)
        params = order.track_profit_params
        sym = Symbol(name=position.symbol)
        await sym.init()
        expected_profit = order.expected_profit
        full_points = int(abs(position.price_open - position.tp) / sym.point)
        trail = params['trail']
        captured_points = int(abs(position.price_open - position.price_current) / sym.point)
        extend_start = params['extend_start']
        extend = 1 - extend_start
        sl_points = trail * captured_points
        stops_level = int(sym.trade_stops_level + sym.spread * (1 + extra))
        sl_points = max(sl_points, stops_level)
        sl_value = round(sl_points * sym.point, sym.digits)
        tp_points = full_points * extend
        tp_value = round(tp_points * sym.point, sym.digits)
        change_tp = False
        change_sl = False
        tick = await sym.info_tick()

        if position.type == OrderType.BUY:
            sl = tick.ask - sl_value
            if sl > max(position.sl, position.price_open):
                change_sl = True
            else:
                sl = position.sl

            if position.profit >= (extend_start * expected_profit):
                tp = position.tp + tp_value
                change_tp = True
            else:
                tp = position.tp
        else:
            sl = position.price_current + sl_value
            if sl < min(position.sl, position.price_open):
                change_sl = True
            else:
                sl = position.sl

            if position.profit >= (extend_start * expected_profit):
                tp = position.tp - tp_value
                change_tp = True
            else:
                tp = position.tp

        if change_sl is False and change_tp is False:
            return

        res = await send_order(position=position, sl=sl, tp=tp)
        if res.retcode == 10009:
            params['previous_profit'] = position.profit
            logger.info(f"Modified sl for {position.symbol}:{position.ticket} to {sl}")
            if change_tp:
                new_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                         volume=position.volume, order_type=position.type)
                order.expected_profit = new_profit
                logger.info(f"Extended take profit target for {position.symbol}:{position.ticket} to {tp}")

        elif res.retcode == 10016 and tries > 0:
            await modify_stops(order=order, extra=(extra + 0.01), tries=tries - 1)
        else:
            logger.error(f"Unable to place order due to {res.comment} for {position.symbol}:{position.ticket}")
    except Exception as exe:
        logger.error(f"Trailing profits failed due to {exe}@{exe.__traceback__.tb_lineno}"
                     f" for {order.position.symbol}:{order.position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res
