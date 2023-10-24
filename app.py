"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, RAM, TimeFrame
from traders import SingleTrader, ConfirmTrader
import logging

from symbols import FXSymbol, CryptoSymbol
from strategies import FingerTrap
from utils import closer


logging.basicConfig(level=logging.INFO)

ram = RAM(amount=3, risk_to_reward=2.5)


def build_bot():
    param = {'trend_time_frame': TimeFrame.M15, 'entry_time_frame': TimeFrame.M3}
    bot = Bot()
    st1 = FingerTrap(symbol=FXSymbol(name='BTCUSD'))
    st2 = FingerTrap(symbol=FXSymbol(name='ETHUSD'))
    st3 = FingerTrap(symbol=FXSymbol(name='EURUSD'))
    st4 = FingerTrap(symbol=FXSymbol(name='AUDUSD'))
    st5 = FingerTrap(symbol=FXSymbol(name='GBPUSD'))
    st6 = FingerTrap(symbol=FXSymbol(name='USDJPY'))
    st7 = FingerTrap(symbol=FXSymbol(name='EURJPY'))
    [setattr(s, 'trader', SingleTrader(symbol=s.symbol, ram=ram)) for s in (st1, st2, st3, st4, st5, st6, st7)]
    bot.add_strategies([st1, st2, st3, st4, st5, st6, st7])
    # bot.add_coroutine(closer)
    bot.execute()


build_bot()
