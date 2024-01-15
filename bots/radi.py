"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, ForexSymbol, TimeFrame
import logging

from strategies import RADI
from traders import SimpleTrader

logging.basicConfig(level=logging.INFO)


def build_bot():
    param1 = {'rsi_period': 9, 'rsi_sma': 32}
    param2 = {'rsi_period': 14, 'rsi_sma': 32}
    param3 = {'rsi_period': 14, 'rsi_sma': 20}
    
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index', 'Volatility 50 (1s) Index',
            'Volatility 75 (1s) Index']
    syms = [ForexSymbol(name=sym) for sym in syms]
    st1 = [RADI(symbol=sym, trader=SimpleTrader(symbol=sym)) for sym in syms]
    st2 = [RADI(symbol=sym, params=param1, trader=SimpleTrader(symbol=sym)) for sym in syms]
    st3 = [RADI(symbol=sym, params=param2, trader=SimpleTrader(symbol=sym)) for sym in syms]
    st4 = [RADI(symbol=sym, params=param3, trader=SimpleTrader(symbol=sym)) for sym in syms]
    bot.add_strategies(st1 + st2 + st4 + st3)
    bot.execute()


build_bot()