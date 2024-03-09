"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import PostNut, FingerFractal
from ..closers import monitor
from ..traders import SPTrader
from ..utils import RAM


def build_bot():
    conf = Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1/',
                  use_telegram=True, trailing_stops=True, exit_signals=True, trailing_loss=True, trail_start=0.25,
                  use_full=True, use_ram=True)
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_1.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 (1s) Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index',
            'Volatility 50 (1s) Index', 'Volatility 75 (1s) Index']

    syms = [ForexSymbol(name=sym) for sym in syms]
    pn_sts = [ST(symbol=sym, trader=SPTrader(symbol=sym, ram=RAM(risk_to_reward=1, max_amount=2, min_amount=2)))
              for sym in syms for ST in [PostNut, FingerFractal]]
    bot.add_strategies(pn_sts)
    bot.add_coroutine(monitor)
    bot.execute()
