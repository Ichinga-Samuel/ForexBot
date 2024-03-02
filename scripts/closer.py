import asyncio
from random import randint
from aiomql import ForexSymbol, Order, Account, Positions


async def place_multiple_random_orders():
    """Place multiple random orders"""
    async with Account() as account:
        syms = [ForexSymbol(name=sym.name)for sym in account.symbols if sym.name.startswith('Volatility')]
        [await sym.init() for sym in syms]
        orders = []
        await Positions().close_all()
        while account.equity > 200:
            await account.refresh()
            for sym in syms:
                try:
                    order_type = randint(0, 1)
                    stl = sym.trade_stops_level * 2
                    price, sl, tp = await stop_levels(sym, stl, order_type)
                    order = Order(symbol=sym, type=order_type, volume=sym.volume_max, price=price, sl=sl, tp=tp)
                    orders.append(order)
                except Exception as err:
                    print(f"{err}. Symbol: {sym.name}")
            orders*=5
            await asyncio.gather(*[order.send() for order in orders], return_exceptions=True)
            await asyncio.sleep(5)
            await Positions().close_all()
        await Positions().close_all()


async def stop_levels(sym, points, order_type):
    sl = tp = points * sym.point
    tick = await sym.info_tick()
    if order_type == 0:
        sl, tp = round(tick.ask - sl, sym.digits), round(tick.ask + tp, sym.digits)
        price = tick.ask
    else:
        sl, tp = round(tick.bid + sl, sym.digits), round(tick.bid - tp, sym.digits)
        price = tick.bid
    return price, sl, tp


async def close_all():
    async with Account() as _:
        await Positions().close_all()
