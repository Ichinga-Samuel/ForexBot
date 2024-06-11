"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging
import logging.config
import json

from aiomql import Bot, ForexSymbol, Config

from ..traders.sp_trader import SPTrader
from ..strategies import FingerTrap, FFATR
from ..closers import monitor, atr_trailer


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
        params = {"atr_factor": 0.75}
        ff_sts = [FFATR(symbol=sym,
                        trader=SPTrader(symbol=sym, profit_tracker=atr_trailer,
                                        track_profit_params={'trail_start': 0.1}),
                        params=params.copy()) for sym in v_syms]
        ft_sts = [FingerTrap(symbol=sym, trader=SPTrader(symbol=sym, profit_tracker=atr_trailer,
                                                         track_profit_params={'trail_start': 0.1}),
                             params=params.copy()) for sym in v_syms]
        bot.add_strategies(ff_sts + ft_sts)
        bot.add_coroutine(monitor)
        bot.execute()
    except Exception as exe:
        logging.error(f'An error occurred in function build_bot {exe}')
