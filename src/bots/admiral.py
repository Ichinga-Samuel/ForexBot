import logging
from datetime import time
from aiomql import Bot, Config, Sessions, Session, TimeFrame

from ..symbols import AdmiralSymbol
from ..closers import closer
from ..strategies import PostNut, FingerTrap


def build_bot():
    Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral/')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    london = Session(start=time(10, 0), end=time(16, 0), name='london')
    intl = Session(start=time(10, 0), end=time(20, 0), name='london')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]

    sts = [FingerTrap(symbol=sym, sessions=Sessions(london)) for sym in syms]
    sts1 = [PostNut(symbol=sym, sessions=Sessions(intl)) for sym in syms]
    bot.add_strategies(sts+sts1)
    bot.add_coroutine(closer)
    bot.execute()
