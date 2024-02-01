import logging
from datetime import time
from aiomql import Bot, Config, Sessions, Session

from src import ADIMACD, MFI, RADI, AdmiralSymbol, points_closer


def build_bot():
    Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    london = Session(start=time(12, 0), end=time(16, 0), name='london')
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]
    sts = [Strategy(symbol=sym, sessions=Sessions(london)) for sym in syms for Strategy in [ADIMACD, MFI, RADI]]
    bot.add_strategies(sts)
    bot.add_coroutine(points_closer)
    bot.execute()