import logging
from datetime import time

from aiomql import Bot, Config, Sessions, Session

from ..strategies import FingerFractal, RADI, FractalRADI, FingerTrap, PostNut
from ..symbols import AdmiralSymbol
from ..closers import trailing_stops


def build_bot():
    conf = Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral1/',
                  use_ram=True, tsl=True)

    conf.state['hedge'] = {'reversals': [], 'reversed': {}}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral1.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    intl = Session(start=time(0, 0), end=time(23, 59), name='intl')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]

    sts = [St(symbol=sym, sessions=Sessions(intl)) for sym in syms for St in [RADI, FractalRADI, FingerTrap, PostNut, FingerFractal]]
    bot.add_strategies(sts)
    bot.add_coroutine(trailing_stops)
    bot.execute()
