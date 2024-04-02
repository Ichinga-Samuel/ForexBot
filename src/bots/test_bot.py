"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import FingerFractal, FingerTrap, Momentum, MRMomentum
from ..closers import monitor


def build_bot():
    Config(reload=True, records_dir='records/test/',
           trailing_stops=True, exit_signals=True, trailing_loss=True, use_ram=True)
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/test.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    # syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
    #         'Volatility 100 (1s) Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index',
    #         'Volatility 50 (1s) Index', 'Volatility 75 (1s) Index']
    syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
            'Volatility 75 Index', 'Volatility 10 (1s) Index',
            'Volatility 75 (1s) Index', 'Volatility 50 Index', 'Volatility 50 (1s) Index']
    ff_syms = [ForexSymbol(name=sym) for sym in syms[:1]]
    ff_sts = [St(symbol=sym) for sym in ff_syms for St in [MRMomentum]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
