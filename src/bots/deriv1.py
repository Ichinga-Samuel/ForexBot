"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import PostNut
from ..closers import closer, trailing_stop, hedge


def build_bot():
    conf = Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1/')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_1.log', datefmt='%Y-%m-%d %H:%M:%S')
    conf.state['hedge'] = {'reversals': [], 'reversed': {}}
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 (1s) Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index',
            'Volatility 50 (1s) Index', 'Volatility 75 (1s) Index']
    pn_sts = [PostNut(symbol=ForexSymbol(name=sym)) for sym in syms]
    bot.add_strategies(pn_sts)
    bot.add_coroutine(closer)
    bot.add_coroutine(hedge)
    bot.add_coroutine(trailing_stop)
    bot.execute()
