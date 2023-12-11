"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, RAM, FingerTrap as FT, ForexSymbol, SimpleTrader
import logging

from strategies import FingerTrap, ADI, ATR

logging.basicConfig(level=logging.INFO)

ram = RAM(amount=5, risk_to_reward=2.5, points=15000)
fxram = RAM(amount=2, risk_to_reward=2.5, points=80)


def build_bot():
    bot = Bot()
    fx_symbols = [ForexSymbol(name='EURUSD'), ForexSymbol(name='GBPUSD'), ForexSymbol(name='USDJPY'),
                  ForexSymbol(name='AUDUSD'), ForexSymbol(name='USDCHF'), ForexSymbol(name='USDCAD')]
    crypto_symbols = [ForexSymbol(name='BTCUSD'), ForexSymbol(name='ETHUSD'), ForexSymbol(name="DOGEUSD")]
    fts = [strategy(symbol=s, trader=SimpleTrader(symbol=s, ram=fxram)) for s in fx_symbols for strategy in
           [FingerTrap, ATR, ADI]]
    cts = [strategy(symbol=s, trader=SimpleTrader(symbol=s, ram=ram)) for s in crypto_symbols for strategy in
           [FingerTrap, ATR, ADI]]
    bot.add_strategies(fts + cts)
    bot.execute()


build_bot()