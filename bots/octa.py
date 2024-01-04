"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, ForexSymbol
import logging

from strategies import ADIMACD, ADIMACD2
from traders import FXTrader, MultiTrader, RAM

logging.basicConfig(level=logging.INFO)


def build_bot():
    bot = Bot()
    fx_symbols = [ForexSymbol(name='EURUSD'), ForexSymbol(name='GBPUSD'), ForexSymbol(name='USDJPY'),
                  ForexSymbol(name='AUDUSD'), ForexSymbol(name='NZDUSD'), ForexSymbol(name='USDCAD')]
    crypto_symbols = [ForexSymbol(name='BTCUSD'), ForexSymbol(name='ETHUSD'), ForexSymbol(name="SOLUSD")]

    sts = [ADIMACD2(symbol=s, trader=MultiTrader(symbol=s)) for s in fx_symbols]
    cts = [ADIMACD2(symbol=s, trader=MultiTrader(symbol=s, ram=RAM(points=0))) for s in crypto_symbols]
    bot.add_strategies(cts)
    bot.execute()


build_bot()