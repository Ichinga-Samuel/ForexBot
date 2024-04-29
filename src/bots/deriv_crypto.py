"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import FingerTrap
from ..closers import monitor
from ..traders import BTrader


def build_bot():
    Config(config_dir='configs', filename='deriv_crypto.json', reload=True, records_dir='records/deriv_crypto/',
           trailing_stops=True, exit_signals=True, use_ram=True, hedging=False, fixed_closer=True, trailing_loss=True)

    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_crypto.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD', 'BNBUSD', 'XRPUSD']
    ff_syms = [ForexSymbol(name=sym) for sym in syms]
    ff_sts = [ST(symbol=sym, trader=BTrader(symbol=sym)) for sym in ff_syms for ST in [FingerTrap]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
