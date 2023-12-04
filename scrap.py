from math import ceil, log10
import asyncio
from pprint import pprint as pp
import logging
from telegram import Update, Bot
from symbols import CryptoSymbol, FXSymbol
from aiomql import Config, Account, Symbol, Order, OrderType, VolumeError, RAM, ForexSymbol, Positions

from traders import ConfirmTrader, SingleTrader

logging.basicConfig(level=logging.WARNING)


async def check():
    async with Account() as acc:
        sym = FXSymbol(name='EURUSD')
        await sym.init()
        print(sl:=sym.trade_stops_level/10, sp:=sym.spread, ex:=(sp*2)/10, ps:=sl+ex, sym.point, sym.pip, ps*sym.pip)


async def pos():
    async with Account() as acc:
        po = Positions()
        poss = await po.positions_get()
        orders = [po.close(price=p.price_current, ticket=p.ticket, order_type=p.type, volume=p.volume,
                           symbol=p.symbol) for p in poss]

        await asyncio.gather(*[order for order in orders], return_exceptions=True)

# async def
asyncio.run(check())
