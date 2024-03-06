import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config

from src.utils.sleep import sleep

logger = getLogger(__name__)


async def modify_stop(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        profit = order.get('profit', None)
        pl = [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.50, 45, 0.4, 0.35, 0.3, 0.25, 0.2, 0.25, 0.2, 0.15]
        profit_levels = order.get('profit_levels', getattr(config, 'profit_levels', pl))
        current_level = order.get('current_level', len(profit_levels))
        if not profit:
            profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                          position.price_open, position.tp)
        if profit is None:
            logger.warning(f"Could not get profit for {position.symbol}")
            return

        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        for i, j in enumerate(profit_levels[:current_level]):
            if position.profit > profit * j:
                sym = Symbol(name=position.symbol)
                res = await modify_order(position=position, symbol=sym)
                if res:
                    config.state['profits'][position.ticket]['profit'] = profit
                    config.state['profits'][position.ticket]['profit_levels'] = profit_levels
                    config.state['profits'][position.ticket]['current_level'] = i
                break
    except Exception as err:
        logger.error(f"{err} in modify_trade")


async def modify_order(*, position: TradePosition, symbol: Symbol, trail: float = 0.05):
    try:
        await symbol.init()
        tick = await symbol.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        spread = symbol.spread
        min_points = symbol.trade_stops_level + spread
        points = (abs(position.price_open - position.tp) / symbol.point) * trail
        points = max(points, min_points)
        dp = round(points * symbol.point, symbol.digits)
        if position.type == OrderType.BUY:
            sl = price - dp
        else:
            sl = price + dp
        order = Order(position=position.ticket, sl=sl, action=TradeAction.SLTP, tp=position.tp)
        res = await order.send()
        if res.retcode == 10009:
            logger.info(f"Successfully modified {symbol}")
            return True
        else:
            logger.error(f"Could not modify order {res.comment} for {symbol}")
            return False
    except Exception as err:
        logger.error(f"{err} in trailing_stop.modify_order")


# change the interval to two minutes
async def trailing_stop(*, tf: TimeFrame = TimeFrame.M2):
    print('Trailing stop started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            await asyncio.gather(*[modify_stop(position=position) for position in positions if position.profit > 0], return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function trailing_stop {exe}')
            await sleep(tf.time)
