import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config

from ..utils.sleep import sleep

logger = getLogger(__name__)


async def modify_stop(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        expected_profit = order.get('expected_profit', None)
        trail = order.get('trail', 0.15)
        if not expected_profit:
            expected_profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                                   position.price_open, position.tp)
            config.state['profits'][position.ticket]['expected_profit'] = expected_profit
        if expected_profit is None:
            logger.warning(f"Could not get profit for {position.symbol}")
            return
        if position.profit < (expected_profit * trail):
            return
        sym = Symbol(name=position.symbol)
        await sym.init()
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        taken_points = abs(position.price_open - price) / sym.point
        trail_points = (1 - trail) * taken_points
        min_points = sym.trade_stops_level + sym.spread
        points = max(trail_points, min_points)
        dp = round(points * sym.point, sym.digits)
        sl, tp = (price - dp, price + dp) if position.type == OrderType.BUY else (price + dp, price - dp)
        order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
        res = await order.send()
        if res.retcode == 10009:
            logger.warning(f"Successfully modified {res.comment} at {dp} for {position.symbol}")
        else:
            logger.error(f"Could not modify order {res.comment}")
    except Exception as err:
        logger.error(f"{err} in modify_trade")


# change the interval to two minutes
async def trailing_stops(*, tf: TimeFrame = TimeFrame.M1):
    print('Trailing stop started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            await asyncio.gather(*[modify_stop(position=position) for position in positions], return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function trailing_stop {exe}')
            await sleep(tf.time)
