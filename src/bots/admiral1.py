import logging
from datetime import time

from aiomql import Bot, Config, Sessions, Session

from ..strategies import FingerFractal, RADI, FractalRADI, SRE
from ..symbols import AdmiralSymbol
from ..closers import closer, trailing_stop, hedge


def build_bot():
    conf = Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral1/')
    conf.state['hedge'] = {'reversals': [], 'reversed': {}}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral1.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    intl = Session(start=time(10, 0), end=time(20, 0), name='london')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]

    sts = [St(symbol=sym, sessions=Sessions(intl)) for sym in syms for St in [FingerFractal, RADI, FractalRADI, SRE]]
    bot.add_strategies(sts)
    bot.add_coroutine(closer)
    bot.add_coroutine(hedge)
    bot.add_coroutine(trailing_stop)
    bot.execute()
