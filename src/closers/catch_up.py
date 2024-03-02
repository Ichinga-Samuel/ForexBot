import asyncio
from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, Config, MetaTrader, TimeFrame

logger = getLogger(__name__)


async def link_up(*, position: TradePosition):
    try:
        if position.profit > 0:
            return
        config = Config()
        order = config.state.setdefault('profits', {}).get(position.ticket, {})
        expected_profit = order.get('expected_profit', None)
        if not expected_profit:
            expected_profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                                   position.price_open, position.tp)
            config.state['profits'][position.ticket]['expected_profit'] = expected_profit
        if expected_profit is None:
            logger.warning(f"Could not get profit for {position.symbol}")
            return
        catch = order.get('catch', 0.3)
        if abs(position.profit) < (expected_profit * catch):
            return
        link_order = Order(type=position.type, symbol=position.symbol, volume=position.volume,
                           comment=f"Link{position.ticket}", sl=position.sl, tp=position.tp)
        res = await link_order.send()
        if res.retcode == 10009:
            logger.warning(f"Successfully linked {res.comment} for {position.symbol}")
            config.state.setdefault('link_ups', {})[position.ticket] = res.order
        else:
            logger.error(f"Could not link order {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function link_up {exe}')


async def loss_close(*, item: tuple[int, int]):
    try:
        pos = Positions()
        first = await pos.positions_get(ticket=item[0])
        first = first[0]
        profit = await pos.mt5.order_calc_profit(first.type, first.symbol, first.volume, first.price_open, first.tp)
        if abs(first.profit) < (profit * 0.6):
            return
        second = await pos.positions_get(ticket=item[1])
        second = second[0]
        tasks = [Positions().close_by(position) for position in [first, second]]
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exe:
        logger.error(f'An error occurred in function loss_close {exe}')


async def net_close(*, item: tuple[int, int]):
    try:
        first = await Positions().positions_get(ticket=item[0])
        profit_1 = first[0].profit if first else 0
        second = await Positions().positions_get(ticket=item[1])
        profit_2 = second[0].profit if second else 0
        if sum([profit_1, profit_2]) > 0:
            positions = first + second
            tasks = [Positions().close_by(position) for position in positions]
            await asyncio.gather(*tasks, return_exceptions=True)
            link_ups = Config().state.get('link_ups', {})
            link_ups.pop(item[0]) if item[0] in link_ups else ...
    except Exception as exe:
        logger.error(f'An error occurred in function close_links {exe}')


async def linkups(*, tf: int = 30):
    print('Link ups started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            link_ups = Config().state.get('link_ups', {})
            link_ups = [link for link in link_ups.items()]
            await asyncio.gather(*[link_up(position=position) for position in positions], return_exceptions=True)
            await asyncio.gather(*[loss_close(item=item) for item in link_ups], return_exceptions=True)
            await asyncio.gather(*[net_close(item=item) for item in link_ups], return_exceptions=True)
            await asyncio.sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function linkups {exe}')
            await asyncio.sleep(tf)
