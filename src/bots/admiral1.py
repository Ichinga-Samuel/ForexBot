import logging
from datetime import time

from aiomql import Bot, Config, Sessions, Session

from ..strategies import FingerFractal, RADI, FractalRADI, FingerTrap, PostNut
from ..symbols import AdmiralSymbol
from ..closers import closer, trailing_stop, alt_hedge
from ..traders import PTrader


def build_bot():
    conf = Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral1/',
                  rev_point=0.5, profit_levels=[0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4,
                                                0.35, 0.3, 0.25, 0.2, 0.25, 0.2, 0.15, 0.10, 0.05])

    conf.state['hedge'] = {'reversals': [], 'reversed': {}}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral1.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    intl = Session(start=time(10, 0), end=time(18, 0), name='intl')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]

    sts = [St(symbol=sym, sessions=Sessions(intl)) for sym in syms for St in [RADI, FractalRADI, FingerTrap, PostNut]]
    bot.add_strategies(sts)
    # bot.add_coroutine(closer)
    bot.add_coroutine(alt_hedge)
    bot.add_coroutine(trailing_stop)
    bot.execute()
