"""A Simple bot that uses the inbuilt FingerTrap strategy"""

import json
import logging
import logging.config

from aiomql import Bot, ForexSymbol, Config

from ..strategies import FFATR, FFCE
from ..closers import monitor


def build_bot():
    log_config = json.load(open(f'src/bots/logging/log_config.json'))
    log_config['handlers']['debug']['filename'] = 'logs/deriv2_debug.log'
    log_config['handlers']['error']['filename'] = 'logs/deriv2_error.log'
    logging.config.dictConfig(log_config)
    config = Config(config_dir='configs', filename='deriv2.json', reload=True, records_dir='records/deriv2/')
    config.load_config()
    config.state['tracked_orders'] = {}

    bot = Bot()
    syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
            'Volatility 75 Index', 'Volatility 10 (1s) Index',
            'Volatility 75 (1s) Index', 'Volatility 50 Index', 'Volatility 50 (1s) Index']

    ff_sts = [ST(symbol=ForexSymbol(name=sym)) for sym in syms for ST in [FFATR, FFCE]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
