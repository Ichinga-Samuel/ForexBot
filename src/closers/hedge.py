import asyncio
from logging import getLogger
from aiomql import Order, OrderType, TradePosition, Symbol, Positions, Config, TradeAction

from ..utils.sleep import sleep

logger = getLogger(__name__)


async def hedge(*, position: TradePosition):
    try:
        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        config = Config()
        order = config.state.setdefault('loss', {}).setdefault(position.ticket, {})
        rev_point = order.get('rev_point', 0.8)
        rev_close_point = order.get('rev_close_point', 0.4)
        hedges = config.state.setdefault('hedges', {})
        sym = Symbol(name=position.symbol)
        await sym.init()
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        points = order.get('points', abs(position.sl - position.price_open) / sym.point)
        taken_points = abs(position.price_open - price) / sym.point
        final_sl = rev_point * points
        rev_close = rev_close_point * points
        if position.profit <= 0 and taken_points >= (rev_point * points):
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
                hedges[position.ticket] = {'rev': res.order, 'sl': final_sl, 'rev_close': rev_close}
                logger.warning(f"Reversed {position.ticket} for {position.symbol} At {position.profit}")
            else:
                logger.error(f"Could not reverse {position.ticket} for {position.symbol} with {res.comment}")
        else:
            return
    except Exception as exe:
        logger.error(f'An error occurred in function hedge {exe}')


async def check_hedge(*, main: int, rev: int):
    try:
        config = Config()
        hedges = config.state.get('hedges', {})
        unhedged = config.state.setdefault('last_chance', {})
        pos = Positions()
        poss = await pos.positions_get(ticket=main)
        main_pos = poss[0] if poss else None
        poss = await pos.positions_get(ticket=rev)
        rev_pos = poss[0] if poss else None
        tick = await Symbol(name=main_pos.symbol).info_tick(name=main_pos.symbol)
        if main_pos and rev_pos:
            data = hedges[main]
            rev_close = data['rev_close']
            close = tick.ask > rev_close if main_pos.type == OrderType.BUY else tick.bid < rev_close
            if close:
                await pos.close_by(rev_pos)
                unhedged[main] = {'sl': data['sl']}
                hedges.pop(main) if main in hedges else ...
            elif rev_pos.profit > 0:
                await extend_tp(position=rev_pos)

        elif not main_pos and rev_pos:
            hedges.pop(main) if main in hedges else ...
            await pos.close_by(rev_pos)

        elif main_pos and not rev_pos:
            hedges.pop(main) if main in hedges else ...

    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge hedging: {exe}')


async def last_chance(position: TradePosition):
    try:
        unhedged = Config().state.get('last_chance', {})
        pos = Positions()
        positions = await pos.positions_get(ticket=position.ticket)
        position = positions[0]
        tick = await Symbol(name=position.symbol).info_tick(name=position.symbol)
        close = tick.ask > position.sl if position.type == OrderType.BUY else tick.bid < position.sl
        if close:
            await pos.close_by(position)
            unhedged.pop(position.ticket) if position.ticket in unhedged else ...
    except Exception as exe:
        logger.error(f'An error occurred in function last_chance {exe}')


async def extend_tp(*, position: TradePosition):
    try:
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        sym = Symbol(name=position.symbol)
        await sym.init()
        points = abs(position.tp - position.price_open) / sym.point
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        taken_points = abs(position.price_open - price) / sym.point
        if position.profit > 0 and taken_points >= (0.95 * points):
            tp_points = 0.05 * points
            dp = round(tp_points * sym.point, sym.digits)
            if position.type == OrderType.BUY:
                tp = price + dp
            else:
                tp = price - dp
            order = Order(ticket=position.ticket, tp=tp, sl=position.sl, symbol=sym, action=TradeAction.SLTP)
            res = await order.send()
            if res.retcode == 10009:
                logger.warning(f"Extended TP for {position.ticket} for {position.symbol} At {position.profit}")
            else:
                logger.error(f"Could not extend TP for {position.ticket} for {position.symbol} with {res.comment}")
        else:
            return
    except Exception as exe:
        logger.error(f'An error occurred in function extend_tp {exe}')


async def hedger(*, tf: int = 30):
    print('Hedging started')
    await sleep(tf)
    conf = Config()
    pos = Positions()
    while True:
        try:
            tasks = []
            positions = await pos.positions_get()
            hedges = conf.state.get('hedges', {})
            hedges = [check_hedge(main=k, rev=v) for k, v in hedges.items()]
            revs = [hedge(position=p) for p in positions if p.profit < 0 and p.ticket not in hedges]
            tasks.extend(hedges)
            tasks.extend(revs)
            await asyncio.gather(*tasks, return_exceptions=True)
            await sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function hedge {exe}')
            await sleep(tf)
