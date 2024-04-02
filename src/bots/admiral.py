import logging
from datetime import time
from aiomql import Bot, Config, Sessions, Session

from ..symbols import AdmiralSymbol
from ..closers import monitor
from ..strategies import FingerFractal, FingerTrap, Momentum, MRMomentum


def build_bot():
    Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral/',
           use_ram=True, trailing_stops=True, exit_signals=True, trailing_loss=True)
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    intl = Session(start=time(10, 0), end=time(18, 0), name='intl')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]
    sts = [St(symbol=sym, sessions=Sessions(intl)) for sym in syms for St in [FingerFractal, FingerTrap, Momentum, MRMomentum]]
    bot.add_strategies(sts)
    bot.add_coroutine(monitor)
    bot.execute()
