import asyncio
from logging import getLogger
from aiomql import Order, OrderType, TradePosition, Symbol, Positions, Config

from ..utils.sleep import sleep

logger = getLogger(__name__)


async def reverse_trade(*, position: TradePosition):
    try:
        Pos = Positions()
        position = await Pos.positions_get(ticket=position.ticket)
        position = position[0]
        config = Config()
        rev_point = getattr(config, 'rev_point', 0.5)
        sym = Symbol(name=position.symbol)
        await sym.init()
        points = abs(position.sl - position.price_open) / sym.point
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        price_points = abs(position.price_open - price) / sym.point
        points_per = price_points / points
        if position.profit <= 0 and points_per >= rev_point:
            tp_points = abs(position.tp - position.price_open) / sym.point
            if position.type == OrderType.BUY:
                order_type = OrderType.SELL
                sl = tick.ask + (points * sym.point)
                tp = tick.ask - (tp_points * sym.point)
            else:
                order_type = OrderType.BUY
                sl = tick.bid - (points * sym.point)
                tp = tick.bid + (tp_points * sym.point)
            comm = getattr(position, 'comment', str(position.ticket)[:6])
            comm = f"Rev{comm}" if 'Rev' not in comm else comm
            order = Order(type=order_type, symbol=sym, sl=sl, tp=tp, volume=position.volume, comment=f"Rev{comm}")
            res = await order.send()
            if res.retcode == 10009:
                await Pos.close_by(position)
            else:
                logger.error(f"Could not reverse {position.ticket} for {position.symbol} with {res.comment}")
        else:
            return
    except Exception as exe:
        logger.error(f'An error occurred in function reverse_trade {exe}')


async def hedge(*, tf: int = 60):
    print('Hedging started')
    await sleep(tf)
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            await asyncio.gather(*[reverse_trade(position=p) for p in positions if p.profit <= 0], return_exceptions=True)
            await sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function hedge {exe}')
            await sleep(tf)
