"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import ADXCrossing
from ..closers import monitor


def build_bot():
    config = Config(config_dir='configs', filename='derived_scalper.json', reload=True,
                    records_dir='records/derived_scalper/')
    config.load_config()
    config.state['order_tracker'] = {}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/derived_scalper.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()

    syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
            'Volatility 75 Index', 'Volatility 10 (1s) Index',
            'Volatility 75 (1s) Index', 'Volatility 50 Index', 'Volatility 50 (1s) Index']

    ff_sts = [ST(symbol=ForexSymbol(name=sym)) for sym in syms for ST in [ADXCrossing]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
