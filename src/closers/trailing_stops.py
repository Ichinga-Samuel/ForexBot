import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config

from ..utils.sleep import sleep
from .trailing_loss import trail_sl
from .closer import OpenTrade
from .fixed_closer import fixed_closer

logger = getLogger(__name__)


async def modify_stop(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        last_profit = order.get('last_profit', 0)
        trail = order.get('trail', 0.25)
        expected_profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                               position.price_open, position.tp)
        if expected_profit is None:
            logger.warning(f"Could not get profit for {position.symbol}")
            return
        if position.profit > (expected_profit * trail) and position.profit > last_profit:
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
            # tdp = round(trail_points * sym.point, sym.digits)
            if position.type == OrderType.BUY:
                sl = price - dp
                tp = price + dp
                tp = position.tp if tp < position.tp else tp
            else:
                sl = price + dp
                tp = price - dp
                tp = position.tp if tp > position.tp else tp
            order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
            res = await order.send()
            if res.retcode == 10009:
                logger.warning(f"Successfully modified {res.comment} at {dp} for {position.symbol}")
                config.state['profits'][position.ticket]['last_profit'] = position.profit
            else:
                logger.error(f"Could not modify order {res.comment}")
    except Exception as err:
        logger.error(f"{err} in modify_stop")


# change the interval to two minutes
async def trailing_stops(*, tf: TimeFrame = TimeFrame.M1, key: str = 'trades'):
    print('Trailing stops started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            config = Config()
            tts = [modify_stop(position=position) for position in positions if position.profit > 0]
            data = config.state.get(key, {})
            open_trades = [OpenTrade(position=p, parameters=data[p.ticket]) for p in positions if p.ticket in data]
            closers = [trade.close() for trade in open_trades]
            tts.extend(closers)
            tsl = getattr(config, 'tsl', False)
            if tsl:
                tsl = [trail_sl(position=position) for position in positions if position.profit < 0]
                tts.extend(tsl)
            uc = getattr(config, 'use_closer', False)
            if uc:
                fc = [fixed_closer(position=position) for position in positions if position.profit < 0]
                tts.extend(fc)
            await asyncio.gather(*tts, return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function trailing_stops {exe}')
            await sleep(tf.time)
