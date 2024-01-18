"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, ForexSymbol, Config
import logging
from src import ADIMACD2, SimpleTrader

Config(config_dir='configs', filename='deriv_demo.json', reload=True)

logging.basicConfig(level=logging.INFO)


def build_bot():
    bot = Bot()
    syms = [ForexSymbol(name='Volatility 50 Index'), ForexSymbol(name='Volatility 50 (1s) Index')]
    st = [ADIMACD2(symbol=sym, trader=SimpleTrader(symbol=sym)) for sym in syms]
    bot.add_strategies(st)
    bot.execute()


build_bot()