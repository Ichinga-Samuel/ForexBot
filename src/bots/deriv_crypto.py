"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import ADXCrossing, FFATR
from ..closers import monitor


def build_bot():
    config = Config(config_dir='configs', filename='deriv_crypto.json', reload=True,
                    records_dir='records/deriv_crypto/')
    config.load_config()
    config.state['order_tracker'] = {}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_crypto.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    crypto_syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD', 'BNBUSD', 'XRPUSD']
    fx_syms = ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF', 'USDJPY']
    crypto_syms = [ForexSymbol(name=sym) for sym in crypto_syms]
    sts = [ST(symbol=sym) for sym in crypto_syms for ST in [FFATR, ADXCrossing]]
    bot.add_strategies(sts)
    bot.add_coroutine(monitor)
    bot.execute()
