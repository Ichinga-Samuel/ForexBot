import logging
from datetime import time

from aiomql import Bot, Config, Sessions, Session

from ..strategies import FingerFractal, FingerTrap, Momentum
from ..symbols import AdmiralSymbol
from ..closers import monitor


def build_bot():
    Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral/',
           use_ram=True, trailing_stops=True, exit_signals=True, trailing_loss=True)

    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral1.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    intl = Session(start=time(0, 0), end=time(23, 59), name='intl')
    syms = [AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name='SOLUSD-T')]

    sts = [St(symbol=sym, sessions=Sessions(intl)) for sym in syms for St in [FingerTrap, Momentum, FingerFractal]]
    bot.add_strategies(sts)
    bot.add_coroutine(monitor)
    bot.execute()
