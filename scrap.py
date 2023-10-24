from math import ceil, log10
import asyncio
from pprint import pprint as pp
import logging
from telegram import Update, Bot
from symbols import CryptoSymbol
from aiomql import Config, Account, Symbol, Order, OrderType, VolumeError, RAM, ForexSymbol, Positions

from traders import ConfirmTrader, SingleTrader

logging.basicConfig(level=logging.WARNING)


async def check():
    async with Account() as acc:
        sym = CryptoSymbol(name='BTCUSD')
        await sym.init()
        for i in range(10):
            trd = SingleTrader(symbol=sym, ram=RAM(amount=2.5))
            await trd.place_trade(order_type=OrderType.SELL, params={'name': 'Testing'})


async def pos():
    async with Account() as acc:
        po = Positions()
        poss = await po.positions_get()
        orders = [po.close(price=p.price_current, ticket=p.ticket, order_type=p.type, volume=p.volume,
                           symbol=p.symbol) for p in poss]

        await asyncio.gather(*[order for order in orders], return_exceptions=True)


asyncio.run(pos())

