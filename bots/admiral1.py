import logging
from datetime import time

from aiomql import Bot, Config, Sessions, Session

from src import FingerFractal, AdmiralSymbol


def build_bot():
    Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral1')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    london = Session(start=time(11, 0), end=time(16, 0), name='london')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]
    sts = [FingerFractal(symbol=sym, sessions=Sessions(london)) for sym in syms]
    bot.add_strategies(sts)
    bot.execute()