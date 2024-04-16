"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import RMomentum, Momentum, MRMomentum, NMomentum, FMomentum, FingerFractal
from ..closers import monitor
# from ..traders import SPTrader
# from ..utils import RAM


def build_bot():
    Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1/',
           trailing_stops=True, exit_signals=False, use_ram=True, hedging=True, fixed_closer=True)

    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_1.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
            'Volatility 75 Index', 'Volatility 10 (1s) Index',
            'Volatility 75 (1s) Index', 'Volatility 50 Index', 'Volatility 50 (1s) Index']

    # ff_syms = [ForexSymbol(name=sym) for sym in syms]

    ff_sts = [FMomentum(symbol=ForexSymbol(name=sym)) for sym in syms]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
