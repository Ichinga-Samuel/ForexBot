"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging
import logging.config
import json

from aiomql import Bot, ForexSymbol, Config

from ..strategies import FingerADX
from ..closers import monitor


def build_bot():
    try:
        log_config = json.load(open(f'src/bots/logging/log_config.json'))
        log_config['handlers']['debug']['filename'] = 'logs/deriv1_debug.log'
        log_config['handlers']['error']['filename'] = 'logs/deriv1_error.log'
        logging.config.dictConfig(log_config)
        config = Config(config_dir='configs', filename='deriv1.json', reload=True,
                        records_dir='records/deriv1/')
        config.load_config()
        config.state['tracked_orders'] = {}
        bot = Bot()

        syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
                'Volatility 75 Index', 'Volatility 10 (1s) Index', 'Volatility 75 (1s) Index', 'Volatility 50 Index',
                'Volatility 50 (1s) Index']
        ff_sts = [ST(symbol=ForexSymbol(name=sym)) for sym in syms for ST in [FingerADX]]
        bot.add_strategies(ff_sts)
        bot.add_coroutine(monitor)
        bot.execute()
    except Exception as exe:
        logging.error(f'An error occurred in function deriv bot {exe}')
