import logging
from datetime import time
from aiomql import Bot, Config, Sessions, Session, TimeFrame

from src import AdmiralSymbol, SCTrader, FingerFractal, SPTrader, RAM


def build_bot():
    Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    london = Session(start=time(10, 0), end=time(16, 0), name='london')
    intl = Session(start=time(10, 0), end=time(20, 0), name='london')
    params = {"ttf": TimeFrame.M15, "tcc": 672, 'trend': 9}
    params2 = {"ttf": TimeFrame.H4, "tcc": 200, 'trend': 2}
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='USDCHF-T')]
    sts = [FingerFractal(symbol=sym, sessions=Sessions(london), params=params, trader=SCTrader(symbol=sym))
           for sym in syms]
    sts1 = [FingerFractal(symbol=sym, sessions=Sessions(intl), params=params2,
                          trader=SPTrader(symbol=sym, multiple=True, risk_to_rewards=[5, 5]))
            for sym in syms]
    bot.add_strategies(sts+sts1)
    bot.execute()