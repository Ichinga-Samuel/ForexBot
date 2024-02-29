import logging
from datetime import time
from aiomql import Bot, Config, Sessions, Session

from ..symbols import AdmiralSymbol
from ..closers import closer, trailing_stop, hedge
from ..strategies import PostNut, FingerFractal, RADI, FractalRADI
from ..traders import PTrader
from ..utils import RAM


def build_bot():
    conf = Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral/')
    conf.state['hedge'] = {'reversals': [], 'reversed': {}}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    intl = Session(start=time(10, 0), end=time(18, 0), name='intl')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]

    sts = [St(symbol=sym, sessions=Sessions(intl), trader=PTrader(symbol=sym, ram=RAM(risk_to_reward=1))) for sym in syms for St in
           [FingerFractal, RADI, FractalRADI, PostNut]]
    bot.add_strategies(sts)
    # bot.add_coroutine(closer)
    bot.add_coroutine(hedge)
    bot.add_coroutine(trailing_stop)
    bot.execute()
