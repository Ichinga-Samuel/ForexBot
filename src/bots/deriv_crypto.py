"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import ADXCrossing, FFATR, FingerADX
from ..closers import monitor


def build_bot():
    config = Config(config_dir='configs', filename='deriv_crypto.json', reload=True,
                    records_dir='records/deriv_crypto/', use_telegram=False)
    config.load_config()
    config.state['tracked_orders'] = {}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_crypto.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    crypto_syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD']
    fx_syms = ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF', 'USDJPY']
    crypto_syms = [ForexSymbol(name=sym) for sym in crypto_syms]
    sts = [ST(symbol=sym) for sym in crypto_syms for ST in [FFATR, ADXCrossing, FingerADX]]
    bot.add_strategies(sts)
    bot.add_coroutine(monitor)
    bot.execute()
