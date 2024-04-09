from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, Config, OrderSendResult

from ..utils.sym_utils import calc_profit

logger = getLogger(__name__)


async def trail_tp(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('winning', {}).setdefault(position.ticket, {})
        last_profit = order.setdefault('last_profit', 0)
        trail = order.setdefault('trail', 0.30)
        trailing = order.get('trailing', False)
        trail_start = order.setdefault('trail_start', 0.375)
        extend_start = order.setdefault('extend_start', 0.80)
        start_trailing = order.get('start_trailing', True)
        current_profit = order.setdefault('current_profit',
                                          await position.mt5.order_calc_profit(position.type, position.symbol,
                                                                               position.volume,
                                                                               position.price_open, position.tp))

        if (start_trailing and ((position.profit > (current_profit * trail_start)) or trailing)
                and position.profit > last_profit):
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(position=position, sym=symbol, current_profit=current_profit, trail=trail,
                               extend_start=extend_start)

    except Exception as err:
        logger.error(f"{err} in modify_stop for {position.symbol}:{position.ticket}")


async def modify_stops(*, position: TradePosition, sym: Symbol, current_profit: float, extra: float = 0.0,
                       tries: int = 4, trail: float = 0.30, extend_start: float = 0.80):
    try:
        config = Config()
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        full_points = int(abs(position.price_open - position.tp) / sym.point)
        trail = (2 / position.profit) or trail
        captured_points = int(abs(position.price_open - position.price_current) / sym.point)
        # remaining_points = int(abs(position.price_current - position.tp) / sym.point)
        extend = 3 / current_profit
        sl_points = int(trail * captured_points)
        stops_level = int(sym.trade_stops_level + sym.spread * (1 + extra))
        sl_points = max(sl_points, stops_level)
        sl_value = round(sl_points * sym.point, sym.digits)
        tp_points = full_points * extend
        tp_value = round(tp_points * sym.point, sym.digits)
        change_tp = False

        if position.type == OrderType.BUY:
            sl = position.price_current - sl_value
            assert sl > max(position.sl, position.price_open)
            if position.profit >= (extend_start * current_profit):
                tp = position.tp + tp_value
                change_tp = True
            else:
                tp = position.tp
        else:
            sl = position.price_current + sl_value
            assert sl < min(position.sl, position.price_open)
            if position.profit >= (extend_start * current_profit):
                tp = position.tp - tp_value
                change_tp = True
            else:
                tp = position.tp

        res = await send_order(position=position, sl=sl, tp=tp)
        if res.retcode == 10009:
            config.state['winning'][position.ticket]['last_profit'] = position.profit
            config.state['winning'][position.ticket]['trailing'] = True
            if change_tp:
                new_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                         volume=position.volume, order_type=position.type)
                config.state['winning'][position.ticket]['current_profit'] = new_profit
                logger.warning(f"Increased TP for {position.symbol}:{position.ticket} {current_profit} {new_profit=}"
                               f"{res.profit=}")
            else:
                logger.warning(f"Trailing Stops for {position.symbol}:{position.ticket} {position.profit=}")
        elif res.retcode == 10016 and tries > 0:
            await modify_stops(position=position, sym=sym, current_profit=current_profit, trail=trail,
                               extra=(extra + 0.01), tries=tries - 1, extend_start=extend_start)
        else:
            logger.error(f"Trailing profits failed due to {res.comment} for {position.symbol}:{position.ticket}")
    except AssertionError as _:
        pass
    except Exception as err:
        logger.error(f"Trailing profits failed due to {err} for {position.symbol}:{position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res
