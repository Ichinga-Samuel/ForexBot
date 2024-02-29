"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import PostNut, FingerTrap, FractalRADI, RADI, FingerFractal
from ..closers import closer, trailing_stop, hedge
from ..utils import RAM
from ..traders import SPTrader


def build_bot():
    conf = Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1/')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_1.log', datefmt='%Y-%m-%d %H:%M:%S')
    conf.state['hedge'] = {'reversals': [], 'reversed': {}}
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 (1s) Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index',
            'Volatility 50 (1s) Index', 'Volatility 75 (1s) Index']
    syms = [ForexSymbol(name=sym) for sym in syms]
    pn_sts = [ST(symbol=sym, trader=SPTrader(symbol=sym, ram=RAM(risk_to_reward=1))) for sym in syms for ST in
              [FractalRADI, RADI, FingerTrap, PostNut, FingerFractal]]
    bot.add_strategies(pn_sts)
    # bot.add_coroutine(closer)
    bot.add_coroutine(hedge)
    bot.add_coroutine(trailing_stop)
    bot.execute()
