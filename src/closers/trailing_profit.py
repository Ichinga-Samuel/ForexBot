from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, OrderSendResult

from ..utils.order_utils import calc_profit
from .track_order import OpenOrder
logger = getLogger(__name__)


async def trail_tp(*, position: TradePosition, order: OpenOrder):
    try:
        print('Using Trailing Take Profit')
        params = order.track_profit_params
        start_trailing = params['start_trailing']
        if start_trailing and position.profit >= params['trail_start']:
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(position=position, params=params)
    except Exception as err:
        logger.error(f"{err} in modify_stop for {position.symbol}:{position.ticket}")


async def modify_stops(*, position: TradePosition, params: dict, extra: float = 0.0, tries: int = 4):
    try:
        pos = Positions()
        position = await pos.position_get(ticket=position.ticket)
        sym = Symbol(name=position.symbol)
        await sym.init()

        previous_profit = params['previous_profit']
        if position.profit <= previous_profit:
            return

        expected_profit = params['expected_profit']
        full_points = int(abs(position.price_open - position.tp) / sym.point)
        trail = params['trail']
        trail = trail / expected_profit
        captured_points = int(abs(position.price_open - position.price_current) / sym.point)
        extend_by = params['extend_by']
        extend = extend_by / expected_profit
        sl_points = trail * captured_points
        stops_level = int(sym.trade_stops_level + sym.spread * (1 + extra))
        sl_points = max(sl_points, stops_level)
        sl_value = round(sl_points * sym.point, sym.digits)
        tp_points = full_points * extend
        tp_value = round(tp_points * sym.point, sym.digits)
        change_tp = False
        change_sl = False
        extend_start = params['extend_start']
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
            logger.warning(f"No changes made to stops for {position.symbol}:{position.ticket}")
            return
        res = await send_order(position=position, sl=sl, tp=tp)
        if res.retcode == 10009:
            params['previous_profit'] = position.profit
            params['trailing'] = True
            logger.error(f"Modified sl for {position.symbol}:{position.ticket} to {sl}")
            if change_tp:
                new_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                         volume=position.volume, order_type=position.type)
                params['expected_profit'] = new_profit
                logger.error(f"Extended take profit target for {position.symbol}:{position.ticket} to {new_profit}")

        elif res.retcode == 10016 and tries > 0:
            await modify_stops(position=position, params=params, extra=(extra + 0.01), tries=tries - 1)
        else:
            logger.error(f"Unable to place order due to {res.comment} for {position.symbol}:{position.ticket}")
    except Exception as err:
        logger.error(f"Trailing profits failed due to {err} for {position.symbol}:{position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res
