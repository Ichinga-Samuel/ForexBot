import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config

from ..utils.sleep import sleep

logger = getLogger(__name__)


async def modify_stops(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        last_profit = order.get('last_profit', 0)
        trail = order.get('trail', 0.05)
        trail_start = order.get('trail_start', 0.25)
        initial_profit = order.get('initial_profit')
        current_profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                              position.price_open, position.tp)
        if (initial_profit or current_profit) is None:
            logger.warning(f"Could not get profit for {position.symbol}")
            return
        initial_profit = initial_profit or current_profit
        if position.profit > (initial_profit * trail_start) and position.profit > last_profit:
            sym = Symbol(name=position.symbol)
            await sym.init()
            points = abs(position.price_open - position.tp) / sym.point
            tick = await sym.info_tick()
            price = tick.ask if position.type == OrderType.BUY else tick.bid
            trail_points = trail * points
            min_points = sym.trade_stops_level + sym.spread
            logger.error(f"Trail points: {trail_points}, Min points: {min_points}")
            points = max(trail_points, min_points)
            dp = round(points * sym.point, sym.digits)
            if position.type == OrderType.BUY:
                sl = price - dp
                if sl > position.price_open:
                    tp = price + dp
                    tp = position.tp if tp < position.tp else tp
                    await send_order(position=position, sl=sl, tp=tp, config=config)
            else:
                sl = price + dp
                if sl < position.price_open:
                    tp = price - dp
                    tp = position.tp if tp > position.tp else tp
                    await send_order(position=position, sl=sl, tp=tp, config=config)
    except Exception as err:
        logger.error(f"{err} in modify_stop")


async def send_order(*, position: TradePosition, sl: float, tp: float, config: Config):
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    if res.retcode == 10009:
        logger.warning(f"Successfully modified {res.comment} {position.symbol}")
        config.state['profits'][position.ticket]['last_profit'] = position.profit
    else:
        logger.error(f"Could not modify order {res.comment}")


# change the interval to two minutes
async def trailing_stops(*, tf: TimeFrame = TimeFrame.M1):
    print('Trailing stops started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            tts = [modify_stops(position=position) for position in positions if position.profit > 0]
            await asyncio.gather(*tts, return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function trailing_stops {exe}')
            await sleep(tf.time)
