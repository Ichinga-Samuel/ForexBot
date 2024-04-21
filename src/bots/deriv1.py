"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import RMomentum, Momentum, MRMomentum, NMomentum, FMomentum, FingerFractal
from ..closers import monitor
# from ..traders import SPTrader
# from ..utils import RAM


def build_bot():
    Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1/',
           trailing_stops=True, exit_signals=True, use_ram=True, hedging=True, fixed_closer=True)

    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_1.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD', 'LTCUSD', 'AVAUSD']

    # ff_syms = [ForexSymbol(name=sym) for sym in syms]
    ff_sts = [FingerFractal(symbol=ForexSymbol(name=sym)) for sym in syms]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
