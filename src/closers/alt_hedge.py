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
        hedges = config.state.setdefault('hedge', {})
        reversals = hedges.setdefault('reversals', [])
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
            order = Order(type=order_type, symbol=sym, sl=sl, tp=tp, volume=position.volume, comment=f"Rev{comm}")
            res = await order.send()
            if res.retcode == 10009:
                reversals.append(res.order)
                await Pos.close_by(position)
            else:
                logger.error(f"Could not reverse {position.ticket} for {position.symbol} with {res.comment}")
        else:
            return
    except Exception as exe:
        logger.error(f'An error occurred in function reverse_trade {exe}')


async def close_reversal(*, position: TradePosition):
    try:
        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        config = Config()
        reversals = config.state.get('hedge', {}).get('reversals', [])
        pos = Positions()
        if position.profit <= 0:
            await pos.close_by(position)
            reversals.remove(position.ticket) if position.ticket in reversals else ...
    except Exception as exe:
        logger.error(f'An error occurred in function close_reversal {exe} of hedging')


async def hedge(*, tf: int = 120):
    print('Hedging started')
    await sleep(tf)
    pos = Positions()
    while True:
        try:
            revs = Config().state.get('hedge', {}).get('reversals', [])
            positions = await pos.positions_get()
            await asyncio.gather(*[reverse_trade(position=p) for p in positions if p.profit <= 0 and p.ticket
                                   not in revs], return_exceptions=True)
            await asyncio.gather(*[close_reversal(position=p) for p in positions if p.ticket in revs],
                                 return_exceptions=True)
            await sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function hedge {exe}')
            await sleep(tf)
