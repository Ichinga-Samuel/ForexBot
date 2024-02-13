import logging
from datetime import time
from aiomql import Bot, Config, Sessions, Session, TimeFrame, FingerTrap

from ..symbols import AdmiralSymbol
from ..traders import SPTrader
from ..closers import ema_closer, closer
from ..strategies import PostNut


def build_bot():
    Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral/')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    london = Session(start=time(10, 0), end=time(16, 0), name='london')
    intl = Session(start=time(10, 0), end=time(20, 0), name='london')
    params = {'closer': ema_closer}
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]

    sts = [FingerTrap(symbol=sym, sessions=Sessions(london), params=params, trader=SPTrader(symbol=sym))
           for sym in syms]
    sts1 = [PostNut(symbol=sym, sessions=Sessions(intl)) for sym in syms]
    bot.add_strategies(sts+sts1)
    bot.add_coroutine(closer, tf=TimeFrame.M5)
    bot.execute()
