"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import ADXATR, ADXCrossing, FFATR
from ..closers import monitor


def build_bot():
    config = Config(config_dir='configs', filename='deriv_crypto.json', reload=True,
                    records_dir='records/deriv_crypto/')
    config.load_config()
    config.state['order_tracker'] = {}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_crypto.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD', 'BNBUSD', 'XRPUSD']
    # "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD"
    ff_syms = [ForexSymbol(name=sym) for sym in syms]
    ff_sts = [ST(symbol=sym) for sym in ff_syms for ST in [FFATR, ADXCrossing, ADXATR]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
