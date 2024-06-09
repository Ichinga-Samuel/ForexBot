"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging
import logging.config
import json

from aiomql import Bot, ForexSymbol, Config

from ..strategies import FFATR
from ..closers import monitor


def build_bot():
    try:
        log_config = json.load(open(f'src/bots/logging/log_config.json'))
        log_config['handlers']['debug']['filename'] = 'logs/deriv_crypto_debug.log'
        log_config['handlers']['error']['filename'] = 'logs/deriv_crypto_error.log'
        logging.config.dictConfig(log_config)
        config = Config(config_dir='configs', filename='deriv_crypto.json', reload=True,
                        records_dir='records/deriv_crypto/', use_telegram=False)
        config.load_config()
        config.state['tracked_orders'] = {}
        bot = Bot()
        crypto_syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD']
        crypto_syms = [ForexSymbol(name=sym) for sym in crypto_syms]
        csts = [FFATR(symbol=sym) for sym in crypto_syms]
        bot.add_strategies(csts)
        bot.add_coroutine(monitor)
        bot.execute()
    except Exception as exe:
        logging.error(f'An error occurred in function crypto bot {exe}')
