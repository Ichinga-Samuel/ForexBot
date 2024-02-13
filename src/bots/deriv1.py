"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config, TimeFrame, FingerTrap

from ..strategies import PostNut
from ..traders import SPTrader
from ..closers import closer, ema_closer


def build_bot():
    Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1/')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_1.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 (1s) Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index',
            'Volatility 50 (1s) Index', 'Volatility 75 (1s) Index']
    fx_syms = [ForexSymbol(name=sym) for sym in syms]
    parameters = {'closer': ema_closer}
    ft_sts = [FingerTrap(symbol=sym, trader=SPTrader(track_trades=True, symbol=sym), params=parameters) for sym in fx_syms]
    pn_sts = [PostNut(symbol=ForexSymbol(name=sym)) for sym in syms]

    bot.add_strategies(pn_sts+ft_sts)
    bot.add_coroutine(closer, tf=TimeFrame.M5)
    bot.execute()
