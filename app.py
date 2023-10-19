"""
A Simple bot that uses the inbuilt FingerTrap strategy to trade on EURUSD, GBPUSD, EURGBP, EURAUD.
"""
from aiomql import Bot, ForexSymbol, FingerTrap
from traders import SingleTrader
import logging

logging.basicConfig(level=logging.INFO)


def build_bot():
    bot = Bot()
    pas = {'pips': 10, 'trend_candles_count': 500}
    st = FingerTrap(symbol=ForexSymbol(name='EURUSD'), params=pas)
    st4 = FingerTrap(symbol=ForexSymbol(name='AUDUSD'), params=pas)
    st1 = FingerTrap(symbol=ForexSymbol(name='GBPUSD'), params=pas)
    st2 = FingerTrap(symbol=ForexSymbol(name='USDJPY'), params=pas)
    st3 = FingerTrap(symbol=ForexSymbol(name='EURJPY'), params=pas)
    [setattr(s, 'trader', SingleTrader(symbol=s.symbol)) for s in (st2, st3, st1, st, st4)]
    bot.add_strategies([st, st2, st3, st4, st1])
    bot.execute()


build_bot()
