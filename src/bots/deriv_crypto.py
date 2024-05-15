"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from ..strategies import ADXScalper, ADXScalper2, ADXATR, ADXCrossing
from ..closers import monitor


def build_bot():
    config = Config(config_dir='configs', filename='deriv_crypto.json', reload=True,
                    records_dir='records/deriv_crypto/',
                    trailing_stops=True, exit_signals=True, use_ram=True, hedging=True, fixed_closer=True,
                    trailing_loss=False, use_telegram=False, atr_trailer=True)

    config.state['winning'] = {}
    config.state['losing'] = {}
    config.state['fixed_closer'] = {}
    config.state['hedges'] = {}
    config.state['no_hedge'] = []
    config.state['atr_trailer'] = {}
    config.state['tracked_trades'] = {}
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv_crypto.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['ETHUSD', 'BTCUSD', 'DOGUSD', 'SOLUSD', 'ADAUSD', 'BNBUSD', 'XRPUSD', "EURUSD", "GBPUSD", "AUDUSD",
            "NZDUSD", "USDJPY", "USDCHF", "USDCAD"]
    ff_syms = [ForexSymbol(name=sym) for sym in syms]
    ff_sts = [ST(symbol=sym) for sym in ff_syms for ST in [ADXScalper2, ADXScalper, ADXCrossing, ADXATR]]
    bot.add_strategies(ff_sts)
    bot.add_coroutine(monitor)
    bot.execute()
