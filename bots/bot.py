"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, RAM, FingerTrap, ForexSymbol, SimpleTrader
import logging

from strategies import ADI, ATR, ADIMACD
from traders import SimpleTrader

logging.basicConfig(level=logging.INFO)

ram = RAM(amount=3, risk_to_reward=1.5, points=0)
fxram = RAM(amount=3, risk_to_reward=1.5, points=100)


def build_bot():
    bot = Bot()
    fx_symbols = [ForexSymbol(name='EURUSD'), ForexSymbol(name='GBPUSD'), ForexSymbol(name='USDJPY'),
                  ForexSymbol(name='AUDUSD'), ForexSymbol(name='NZDUSD'), ForexSymbol(name='USDCAD')]
    crypto_symbols = [ForexSymbol(name='BTCUSD'), ForexSymbol(name='ETHUSD'), ForexSymbol(name="LTCUSD")]

    fts = [strategy(symbol=s, trader=SimpleTrader(symbol=s, ram=fxram)) for s in fx_symbols for strategy in
           [ADI, FingerTrap]]
    cts = [strategy(symbol=s, trader=SimpleTrader(symbol=s, ram=ram)) for s in crypto_symbols for strategy in
           [ADI, FingerTrap]]
    bot.add_strategies(fts + cts)
    bot.execute()


build_bot()