"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from aiomql import Bot, RAM, TimeFrame, FingerTrap as FT, ForexSymbol, SimpleTrader
import logging

from strategies import FingerTrap, ADI, ATR
from traders import ConfirmationTrader

logging.basicConfig(level=logging.INFO)

ram = RAM(amount=5, risk_to_reward=2.5, points=15000)
fxram = RAM(amount=2, risk_to_reward=2.5, points=80)
# config = Config()
# print(config.telegram_bot_token)

fx_symbols = [
    ForexSymbol(name="EURUSD"),
    ForexSymbol(name="AUDUSD"),
    ForexSymbol(name="USDCHF"),
    ForexSymbol(name="GBPUSD"),
    ForexSymbol(name="USDJPY"),
    ForexSymbol(name="NZDUSD"),
    ForexSymbol(name="USDCAD"),
    ForexSymbol(name="EURGBP"),
    ForexSymbol(name="EURJPY"),
    ForexSymbol(name="EURCHF"),
    ForexSymbol(name="EURAUD"),
    ForexSymbol(name="EURNZD"),
    ForexSymbol(name="EURCAD"),
    ForexSymbol(name="GBPJPY"),
    ForexSymbol(name="GBPCHF"),
    ForexSymbol(name="GBPAUD"),
    ForexSymbol(name="GBPNZD"),
    ForexSymbol(name="GBPCAD"),
    ForexSymbol(name="CHFJPY"),
    ForexSymbol(name="AUDJPY"),
    ForexSymbol(name="AUDCHF"),
    ForexSymbol(name="AUDNZD"),
    ForexSymbol(name="AUDCAD"),
    ForexSymbol(name="NZDJPY"),
    ForexSymbol(name="USDCAD"),
    ForexSymbol(name="NZDCHF"),
    ForexSymbol(name="NZDCAD"),
    ForexSymbol(name="CADCHF"),
    ForexSymbol(name="CADJPY")
]
crypto_symols = [
    ForexSymbol(name="BTCUSD"),
    ForexSymbol(name="ETHUSD"),
    ForexSymbol(name="LTCUSD"),
    ForexSymbol(name="XRPUSD"),
    ForexSymbol(name="BCHUSD"),
    ForexSymbol(name="ADAUSD"),
    ForexSymbol(name="DOGEUSD"),
    ForexSymbol(name="DOTUSD"),
    ForexSymbol(name="SOLUSD"),
    ForexSymbol(name="AVAXUSD"),
    ForexSymbol(name="LINKUSD"),
    ForexSymbol(name="FILUSD"),
    ForexSymbol(name="UNIUSD"),
    ForexSymbol(name="AAVEUSD"),
    ForexSymbol(name="ATOMUSD"),
    ForexSymbol(name="ALGOUSD"),
    ForexSymbol(name="AXSUSD"),
    ForexSymbol(name="NEARUSD"),
    ForexSymbol(name="MATICUSD"),
]


def build_bot():
    bot = Bot()
    fx_symbols = [ForexSymbol(name='EURUSD'), ForexSymbol(name='GBPUSD'), ForexSymbol(name='USDJPY')]
    sts = [ATR(symbol=s, trader=ConfirmationTrader(symbol=s, ram=fxram)) for s in fx_symbols]
    bot.add_strategies(sts)
    # sts = [(FingerTrap(symbol=s, trader=ConfirmationTrader(symbol=s, ram=fxram)), ADI(symbol=s), ATR(symbol=s)) for s in fx_symbols]
    # sts = [s for sy in sts for s in sy]
    # cts = [(FingerTrap(symbol=s, trader=ConfirmationTrader(symbol=s, ram=ram)), ADI(symbol=s), ATR(symbol=s)) for s in crypto_symols]
    # cts = [s for sy in cts for s in sy]
    # [bot.add_strategy(s) for s in sts + cts]
    # bot.add_coroutine(closer)
    bot.execute()


build_bot()