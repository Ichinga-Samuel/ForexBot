"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging
from datetime import time

from aiomql import Bot, ForexSymbol, Config, Session, Sessions

from ..strategies import ADXCrossing, FFATR, FingerTrap
from ..closers import monitor


def build_bot():
    config = Config(config_dir='configs', filename='deriv_crypto.json', reload=True,
                    records_dir='records/deriv_crypto/', use_telegram=False)
    config.load_config()
    config.state['tracked_orders'] = {}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_crypto.log', datefmt='%Y-%m-%d %H:%M')
    bot = Bot()
    crypto_syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD']
    fx_syms = ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCHF', 'USDJPY']
    crypto_syms = [ForexSymbol(name=sym) for sym in crypto_syms]
    london_new_york = Session(start=time(hour=10), end=time(hour=17), name='London/New York')
    csts = [ST(symbol=sym) for sym in crypto_syms for ST in [ADXCrossing, FingerTrap]]
    fsts = [ST(symbol=ForexSymbol(name=sym), sessions=Sessions(london_new_york))
            for sym in fx_syms for ST in [ADXCrossing, FingerTrap]]
    sts = csts + fsts
    bot.add_strategies(sts)
    bot.add_coroutine(monitor)
    bot.execute()
