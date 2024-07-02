"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging
import logging.config
import json

from aiomql import Bot, ForexSymbol, Config, TimeFrame

from ..traders.sp_trader import SPTrader
from ..strategies import FFATR, Chaos
from ..closers import monitor


def build_bot():
    try:
        log_config = json.load(open(f'src/bots/logging/log_config.json'))
        log_config['handlers']['debug']['filename'] = 'logs/deriv_scalper_debug.log'
        log_config['handlers']['error']['filename'] = 'logs/deriv_scalper_error.log'
        logging.config.dictConfig(log_config)

        config = Config(config_dir='configs', filename='deriv_scalper.json', reload=True,
                        records_dir='records/deriv_scalper/')
        config.load_config()
        config.state['tracked_orders'] = {}
        bot = Bot()
        syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
                'Volatility 75 Index', 'Volatility 10 (1s) Index',
                'Volatility 75 (1s) Index', 'Volatility 50 Index', 'Volatility 50 (1s) Index']
        v_syms = [ForexSymbol(name=sym) for sym in syms]

        ff_sts = [FFATR(symbol=sym,
                        trader=SPTrader(symbol=sym, track_profit_params={'trail_start': 0.25}),
                        params={'etf': TimeFrame.M10, 'timeout': TimeFrame.H2, 'htf': TimeFrame.H1}) for sym in v_syms]
        c_sts = [Chaos(symbol=sym) for sym in v_syms]
        bot.add_strategies(ff_sts + c_sts)
        bot.add_coroutine(monitor)
        bot.execute()
    except Exception as exe:
        logging.error(f'An error occurred in function build_bot {exe}')
