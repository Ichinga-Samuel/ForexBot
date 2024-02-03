"""A Simple bot that uses the inbuilt FingerTrap strategy"""
import logging

from aiomql import Bot, ForexSymbol, Config

from src import FractalRADI, FingerFractal, FractalMFI


def build_bot():
    Config(config_dir='configs', filename='deriv_demo_1.json', reload=True, records_dir='records/deriv1')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 (1s) Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index',
            'Volatility 50 (1s) Index', 'Volatility 75 (1s) Index']

    fr_syms = [ForexSymbol(name='Volatility 50 Index'), ForexSymbol(name='Volatility 10 (1s) Index'),
               ForexSymbol(name='Volatility 10 (1s) Index')]
    fr_sts = [FractalRADI(symbol=sym) for sym in fr_syms]

    ff_syms = [ForexSymbol(name=sym) for sym in syms]

    ff_sts = [FingerFractal(symbol=sym) for sym in ff_syms]

    fm_syms = [ForexSymbol(name=sym) for sym in syms]
    fm_sts = [FractalMFI(symbol=sym) for sym in fm_syms]

    bot.add_strategies(fr_sts + ff_sts + fm_sts)
    bot.execute()