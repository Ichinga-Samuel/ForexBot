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
        trail = order.get('trail', 0.05)
        trail_start = order.get('trail_start', 0.5)
        ts = getattr(config, 'trail_start', 0.95)
        trail_start = trail_start or ts
        initial_profit = order.get('initial_profit')
        current_profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                              position.price_open, position.tp)
        if (initial_profit or current_profit) is None:
            logger.warning(f"Could not get profit for {position.symbol}")
            return
        initial_profit = initial_profit or current_profit
        print(f"{current_profit=} pc={current_profit * trail_start} {last_profit=} mow={position.profit}")
        if position.profit > (current_profit * trail_start) and position.profit > last_profit:
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(position=position, trail=trail, sym=symbol, config=config, last_profit=last_profit)

    except Exception as err:
        logger.error(f"{err} in modify_stop")


async def modify_stops(*, position: TradePosition, trail: float, sym: Symbol, config: Config, extra=0.0, tries=3,
                       last_profit=0):
    try:
        assert position.profit > last_profit
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        points = abs(position.price_open - position.tp) / sym.point
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        trail_points = trail * points
        min_points = sym.trade_stops_level + sym.spread + (sym.spread * extra)
        points = max(trail_points, min_points)
        dp = round(points * sym.point, sym.digits)
        dt = round(trail_points * sym.point, sym.digits)
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
