from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, Config, OrderSendResult

from ..utils.sym_utils import calc_profit

logger = getLogger(__name__)


async def trail_tp(*, position: TradePosition):
    try:
        config = Config()
        order = config.state['winning'][position.ticket]
        start_trailing = order['start_trailing']

        if start_trailing:
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(position=position, order=order)

    except Exception as err:
        logger.error(f"{err} in modify_stop for {position.symbol}:{position.ticket}")


async def modify_stops(*, position: TradePosition, order: dict, extra: float = 0.0, tries: int = 4):
    try:
        config = Config()
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        sym = Symbol(name=position.symbol)
        await sym.init()

        fixed_closer = config.state['fixed_closer'][position.ticket]
        if order['use_trails']:
            trails = order['trails']
            keys = sorted(trails.keys())
            if len(keys):
                take_profit = keys[0]
                adjust = trails[take_profit]
                if position.profit >= take_profit:
                    fixed_closer['close'] = True
                    fixed_closer['cut_off'] = adjust
                    trails.pop(take_profit)
                    if len(trails) == 0:
                        order['use_trails'] = False

        last_profit = order['last_profit']
        trail_start = order['trail_start']
        if position.profit < trail_start and position.profit < last_profit:
            return

        current_profit = order['current_profit']
        full_points = int(abs(position.price_open - position.tp) / sym.point)
        trail = order['trail']
        trail = trail / current_profit
        captured_points = int(abs(position.price_open - position.price_current) / sym.point)
        extend_by = order['extend_by']
        extend = extend_by / current_profit
        sl_points = int(trail * captured_points)
        stops_level = int(sym.trade_stops_level + sym.spread * (1 + extra))
        sl_points = max(sl_points, stops_level)
        sl_value = round(sl_points * sym.point, sym.digits)
        tp_points = full_points * extend
        tp_value = round(tp_points * sym.point, sym.digits)
        change_tp = False

        extend_start = order['extend_start']
        if position.type == OrderType.BUY:
            sl = position.price_current - sl_value
            try:
                assert sl > max(position.sl, position.price_open), f"current_sl={position.sl} >than new sl={sl} in long"
            except AssertionError as err:
                logger.error(f"Trailing profits failed due to {err} for {position.symbol}:{position.ticket}: AssertionError")
            if position.profit >= (extend_start * current_profit):
                tp = position.tp + tp_value
                change_tp = True
            else:
                tp = position.tp
        else:
            sl = position.price_current + sl_value
            try:
                assert sl < min(position.sl, position.price_open), f"current_sl={position.sl} <than new sl={sl} in short"
            except AssertionError as err:
                logger.error(f"Trailing profits failed due to {err} for {position.symbol}:{position.ticket}: AssertionError")
            if position.profit >= (extend_start * current_profit):
                tp = position.tp - tp_value
                change_tp = True
            else:
                tp = position.tp

        res = await send_order(position=position, sl=sl, tp=tp)
        if res.retcode == 10009:
            order['last_profit'] = position.profit
            order['trailing'] = True
            logger.warning(f"Trailing profits for {position.symbol}:{position.ticket} to {sl=} {tp=}")
            if change_tp:
                new_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                         volume=position.volume, order_type=position.type)
                order['current_profit'] = new_profit

        elif res.retcode == 10016 and tries > 0:
            await modify_stops(position=position, order=order, extra=(extra + 0.01), tries=tries - 1)
        else:
            logger.error(f"Unable to place order due to {res.comment} for {position.symbol}:{position.ticket}")
    except AssertionError as err:
        logger.error(f"Trailing profits failed due to {err} for {position.symbol}:{position.ticket}: AssertionError")
    except Exception as err:
        logger.error(f"Trailing profits failed due to {err} for {position.symbol}:{position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res
