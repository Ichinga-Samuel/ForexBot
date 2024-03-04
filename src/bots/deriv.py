"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import FingerFractal, RADI, FractalRADI, FingerTrap, PostNut
from ..closers import closer, trailing_stop, alt_hedge, trailing_stops


def build_bot():
    Config(config_dir='configs', filename='deriv_demo.json', reload=True, records_dir='records/deriv/',
           use_ram=True, tsl=True)
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/deriv.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 (1s) Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index',
            'Volatility 50 (1s) Index', 'Volatility 75 (1s) Index']

    ff_syms = [ForexSymbol(name=sym) for sym in syms]
    ff_sts = [St(symbol=sym) for sym in ff_syms for St in [FingerFractal, RADI, FractalRADI, FingerTrap, PostNut]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(trailing_stops)
    bot.execute()
