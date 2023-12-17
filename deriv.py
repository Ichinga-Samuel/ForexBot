"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, RAM, FingerTrap, ForexSymbol
import logging

from strategies import MACDonBB, ADI, ATR
from traders import SimpleTrader, ConfirmationTrader, ConfirmationVTrader

logging.basicConfig(level=logging.INFO)

ram = RAM(amount=5, risk_to_reward=2, points=0)


def build_bot():
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index', 'Volatility 50 (1s) Index',
            'Volatility 75 (1s) Index', 'Volatility 100 (1s) Index', 'Volatility 150 (1s) Index',
            'Volatility 250 (1s) Index', 'Volatility 200 (1s) Index', 'Volatility 300 (1s) Index']
    syms = [ForexSymbol(name=sym) for sym in syms]
    dts = [strategy(symbol=s, trader=ConfirmationVTrader(symbol=s, ram=ram)) for s in syms for strategy in [ADI]]
    bot.add_strategies(dts)
    bot.execute()


build_bot()