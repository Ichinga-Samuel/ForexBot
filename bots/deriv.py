"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, FingerTrap, ForexSymbol, TimeFrame
import logging

from strategies import MACDonBB, ADI, ATR, ADIMACD2, FingerTrap2, ADIMACD3
from traders import MultiTrader, RAM, ReverseTrader, SimpleTrader

logging.basicConfig(level=logging.INFO)


def build_bot():
    param1 = {'etf': TimeFrame.M15}
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index', 'Volatility 50 (1s) Index',
            'Volatility 75 (1s) Index']
    syms = [ForexSymbol(name=sym) for sym in syms]
    st1 = [ADIMACD2(symbol=sym, params=param1, trader=ReverseTrader(symbol=sym)) for sym in syms]
    st2 = [ADIMACD2(symbol=sym, trader=ReverseTrader(symbol=sym)) for sym in syms]
    st3 = [ADIMACD3(symbol=sym, trader=SimpleTrader(symbol=sym)) for sym in syms]
    st6 = [ADIMACD3(symbol=sym, params=param1, trader=SimpleTrader(symbol=sym)) for sym in syms]
    st5 = [ADI(symbol=sym, trader=SimpleTrader(symbol=sym, ram=RAM(risk_to_reward=1.1))) for sym in syms]
    st4 = [FingerTrap2(symbol=sym, trader=SimpleTrader(symbol=sym)) for sym in syms]
    bot.add_strategies(st1 + st2 + st4 + st3 + st5 + st6)
    bot.execute()


build_bot()