import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config, OrderSendResult

from ..utils.sleep import sleep

logger = getLogger(__name__)


async def check_stops(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        last_profit = order.get('last_profit', 0)
        trail = getattr(config, 'trail', order.get('trail', 0.15))
        trail_start = getattr(config, 'trail_start', order.get('trail_start', 0.7))
        shift_profit = getattr(config, 'shift_profit', order.get('shift_profit', 0.15))
        current_profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                              position.price_open, position.tp)
        if position.profit > (current_profit * trail_start) and position.profit > last_profit:
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(position=position, trail=trail, sym=symbol, config=config, last_profit=last_profit,
                               shift_profit=shift_profit)
    except Exception as err:
        logger.error(f"{err} in modify_stop")


async def modify_stops(*, position: TradePosition, trail: float, sym: Symbol, config: Config, extra=0.1, tries=3,
                       last_profit=0, shift_profit=0.25):
    try:
        assert position.profit > last_profit
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        points = abs(position.price_open - position.tp) / sym.point
        trail_points = trail * points
        min_points = sym.trade_stops_level
        points = max(trail_points, min_points)
        points = points + sym.spread * (1 + extra)
        dp = round(trail_points * sym.point, sym.digits)
        dt = round(points * shift_profit * sym.point, sym.digits)
        flag = False
        if position.type == OrderType.BUY:
            sl = price - dp
            tp = position.tp + dt
            if sl > position.price_open:
                flag = True
        else:
            sl = price + dp
            tp = position.tp - dt
            if sl < position.price_open:
                flag = True
        if flag:
            res = await send_order(position=position, sl=sl, tp=tp)
            if res.retcode == 10009:
                config.state['profits'][position.ticket]['last_profit'] = position.profit
                logger.warning(f"Modified trade {position.ticket} with {extra=} and {tries=} for {sym}")
            elif res.retcode == 10016 and tries > 0:
                await modify_stops(position=position, trail=trail, sym=sym, config=config, extra=extra + 0.05,
                                   tries=tries - 1, last_profit=last_profit)
            else:
                logger.error(f"Could not modify order {res.comment} with {extra=} and {tries=} for {sym}")
    except Exception as err:
        logger.error(f"{err} in modify_stops")


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
