"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, ForexSymbol, Config
import logging

from src import RADI, MFI, st_closer

Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, root_dir='.')

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/deriv.log', datefmt='%Y-%m-%d %H:%M:%S')


def build_bot():
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index', 'Volatility 50 (1s) Index',
            'Volatility 75 (1s) Index']
    syms = [ForexSymbol(name=sym) for sym in syms]
    sts = [Strategy(symbol=sym) for sym in syms for Strategy in [RADI, MFI]]
    bot.add_strategies(sts)
    bot.add_coroutine(st_closer)
    bot.execute()


build_bot()