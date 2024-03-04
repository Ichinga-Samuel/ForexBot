import logging
from datetime import time
from aiomql import Bot, Config, Sessions, Session

from ..symbols import AdmiralSymbol
from ..closers import trailing_stops
from ..strategies import PostNut, FingerFractal, RADI, FractalRADI, FingerTrap


def build_bot():
    conf = Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral/',
                  use_ram=True, tsl=True)
    conf.state['hedge'] = {'reversals': [], 'reversed': {}}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    intl = Session(start=time(10, 0), end=time(18, 0), name='intl')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]

    sts = [St(symbol=sym, sessions=Sessions(intl)) for sym in syms for St in
           [FingerFractal, RADI, FractalRADI, PostNut, FingerTrap]]
    bot.add_strategies(sts)
    bot.add_coroutine(trailing_stops)
    bot.execute()
