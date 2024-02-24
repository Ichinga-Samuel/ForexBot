import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config

from ..utils.sleep import sleep

logger = getLogger(__name__)


async def modify_stop(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        profit = order.get('profit', None)
        profit_levels = order.get('profit_levels')
        profit_levels = profit_levels or [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5]
        # [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]
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
                res = await modify_order(pos=position, symbol=sym, pp=j)
                if res:
                    config.state['profits'][position.ticket]['profit'] = profit
                    config.state['profits'][position.ticket]['profit_levels'] = profit_levels
                    config.state['profits'][position.ticket]['current_level'] = i
                break
    except Exception as err:
        logger.error(f"{err} in modify_trade")


async def modify_order(*, pos, symbol, extra=0.0, tries=0, pp=0.0):
    try:
        await symbol.init()
        tick = await symbol.info_tick()
        ask = tick.ask
        spread = symbol.spread
        points = (symbol.trade_stops_level + spread + (spread * extra)) * symbol.point
        if pos.type == OrderType.BUY:
            sl = ask - points
        else:
            sl = ask + points
        order = Order(position=pos.ticket, sl=sl, action=TradeAction.SLTP, tp=pos.tp)
        res = await order.send()
        if res.retcode == 10016:
            if tries < 6:
                return await modify_order(pos=pos, symbol=symbol, extra=extra + 0.05, tries=tries + 1)
            else:
                logger.warning(f"Could not modify order {res.comment}")
                return False
        elif res.retcode == 10009:
            logger.warning(f"Successfully modified {res.comment} at {pp} for {pos.symbol}")
            return True
        else:
            logger.error(f"Could not modify order {res.comment}")
            return False
    except Exception as err:
        logger.error(f"{err} in modify_order")


# change the interval to two minutes
async def trailing_stop(*, tf: TimeFrame = TimeFrame.M5):
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
