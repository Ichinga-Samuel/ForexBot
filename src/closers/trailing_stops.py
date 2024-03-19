import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config, OrderSendResult

from ..utils.sleep import sleep
from ..utils.sym_utils import calc_profit

logger = getLogger(__name__)


async def check_stops(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        last_profit = order.get('last_profit', 0)
        trail = getattr(config, 'trail', order.get('trail', 0.15))
        trail_start = getattr(config, 'trail_start', order.get('trail_start', 0.70))
        shift_profit = getattr(config, 'shift_profit', order.get('shift_profit', 0.25))
        current_profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                              position.price_open, position.tp)
        if position.profit > (current_profit * trail_start) and position.profit > last_profit:
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(position=position, trail=trail, sym=symbol, config=config, last_profit=last_profit,
                               shift_profit=shift_profit)
    except Exception as err:
        logger.error(f"{err} in modify_stop for {position.ticket}:{position.symbol}")


async def modify_stops(*, position: TradePosition, trail: float, sym: Symbol, config: Config, extra=0.05, tries=4,
                       last_profit=0, shift_profit=0.25, trail_start=0.70):
    try:
        assert position.profit > last_profit
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        points = abs(position.price_open - position.tp) / sym.point
        trail_points = trail * points
        min_points = sym.trade_stops_level + sym.spread * (1 + extra)
        t_points = max(trail_points, min_points)
        dp = round(t_points * sym.point, sym.digits)
        # dt = round(points * shift_profit * sym.point, sym.digits)
        dt = round(t_points * 0.56 * sym.point, sym.digits)
        flag = False
        if position.type == OrderType.BUY:
            sl = price - dp
            captured_profit = calc_profit(sym=sym, open_price=price, close_price=sl, volume=position.volume,
                                          order_type=OrderType.SELL)
            current_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                         volume=position.volume, order_type=OrderType.BUY)
            logger.warning(f"Captured profit for {position.ticket}:{position.symbol} is {captured_profit}")
            # tp = position.tp + dt
            tp = price + dt
            if captured_profit > trail * current_profit:
                flag = True
        else:
            sl = price + dp
            captured_profit = calc_profit(sym=sym, open_price=price, close_price=sl, volume=position.volume,
                                          order_type=OrderType.BUY)
            current_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                         volume=position.volume, order_type=OrderType.SELL)
            logger.warning(f"Captured profit for {position.ticket}:{position.symbol} is {captured_profit}")
            # tp = position.tp - dt
            tp = price - dt
            if captured_profit > trail_start * current_profit:
                flag = True
        if flag:
            res = await send_order(position=position, sl=sl, tp=tp)
            if res.retcode == 10009:
                config.state['profits'][position.ticket]['last_profit'] = position.profit
                logger.warning(f"Trailed profit for {sym}:{position.ticket} after {4-tries+1} tries")
            elif res.retcode == 10016 and tries > 0:
                await modify_stops(position=position, trail=trail, sym=sym, config=config, extra=extra + 0.05,
                                   tries=tries - 1, last_profit=last_profit)
            else:
                logger.error(f"Trailing profits failed due to {res.comment} after {tries} tries for "
                             f"{position.ticket}:{sym}")
    except Exception as err:
        logger.error(f"Trailing profits failed due to {err} for {position.ticket}:{sym}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res


# change the interval to two minutes
async def trailing_stops(*, tf: TimeFrame = TimeFrame.M1):
    print('Trailing stops started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            tts = [check_stops(position=position) for position in positions if position.profit > 0]
            await asyncio.gather(*tts, return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function trailing_stops {exe}')
            await sleep(tf.time)
