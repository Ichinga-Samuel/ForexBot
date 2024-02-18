import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame

from ..utils.sleep import sleep

logger = getLogger(__name__)


async def modify_stop(*, position: TradePosition):
    try:
        profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                      position.price_open, position.tp)
        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        profit_percent = 0
        for i in [0.8, 0.6, 0.5, 0.25, 0.1, 0.05, 0.025]:
            if position.profit > profit * i:
                profit_percent = i
                break
        else:
            return
        sym = Symbol(name=position.symbol)
        await modify_order(pos=position, symbol=sym, pp=profit_percent)
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
        order = Order(position=pos.ticket, sl=sl, action=TradeAction.SLTP)
        res = await order.send()
        if res.retcode == 10016:
            if tries < 6:
                await modify_order(pos=pos, symbol=symbol, extra=extra + 0.05, tries=tries + 1)
            else:
                logger.warning(f"Could not modify order {res.comment}")
        elif res.retcode == 10009:
            logger.warning(f"Successfully modified {res.comment} at {pp} for {pos.symbol}")
        else:
            logger.error(f"Could not modify order {res.comment}")
    except Exception as err:
        print(f"{err} in modify_order")


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
