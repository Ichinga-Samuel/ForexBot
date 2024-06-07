"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config, TimeFrame

from ..traders.sp_trader import SPTrader
from ..strategies import ADXCrossing, FingerTrap, FFATR
from ..closers import monitor


def build_bot():
    try:
        config = Config(config_dir='configs', filename='derived_scalper.json', reload=True,
                        records_dir='records/derived_scalper/')
        config.load_config()
        config.state['tracked_orders'] = {}
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                            filename='logs/derived_scalper.log', datefmt='%Y-%m-%d %H:%M')
        bot = Bot()

        syms = ['Volatility 10 Index', 'Volatility 100 (1s) Index', 'Volatility 25 Index', 'Volatility 25 (1s) Index',
                'Volatility 75 Index', 'Volatility 10 (1s) Index',
                'Volatility 75 (1s) Index', 'Volatility 50 Index', 'Volatility 50 (1s) Index']
        v_syms = [ForexSymbol(name=sym) for sym in syms]
        params = {"etf": TimeFrame.M30, "tptf": TimeFrame.M30, "exit_timeframe": TimeFrame.M30, "atr_multiplier": 1,
                  "lower_interval": TimeFrame.M10, "higher_interval": TimeFrame.M15, "htf": TimeFrame.H1}
        ff_sts = [ST(symbol=sym, trader=SPTrader(symbol=sym, hedge_on_exit=True), params=params.copy())
                  for sym in v_syms for ST in [FFATR]]
        bot.add_strategies(ff_sts)
        bot.add_coroutine(monitor)
        bot.execute()
    except Exception as exe:
        print(exe)
        logging.error(f'An error occurred in function build_bot {exe}')
