"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import FingerTrap, FingerFractal, RA, ADXScalper
from ..closers import monitor


def build_bot():
    config = Config(config_dir='configs', filename='derived_scalper.json', reload=True,
                    records_dir='records/derived_scalper/',
                    fixed_closer=True, hedging=True, use_ram=True, trailing_stops=True, trailing_loss=False,
                    exit_signals=True, use_telegram=False, atr_trailer=True)
    config.load_config()
    config.state['winning'] = {}
    config.state['losing'] = {}
    config.state['fixed_closer'] = {}
    config.state['hedges'] = {}
    config.state['tracked_trades'] = {}
    config.state['no_hedge'] = []
    config.state['atr_trailer'] = {}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/derived_scalper.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()

    syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
            'Volatility 75 Index', 'Volatility 10 (1s) Index',
            'Volatility 75 (1s) Index', 'Volatility 50 Index', 'Volatility 50 (1s) Index']

    ff_sts = [ST(symbol=ForexSymbol(name=sym)) for sym in syms for ST in [ADXScalper]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
