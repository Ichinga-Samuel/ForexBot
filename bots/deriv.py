"""A Simple bot that uses the inbuilt FingerTrap strategy"""
from pathlib import Path
import logging

from aiomql import Bot, ForexSymbol, Config
from src import FingerFractal, FractalRADI, ADIMACD


def build_bot():
    record_dir = Path.cwd() / 'records' / 'deriv'
    record_dir.mkdir(parents=True, exist_ok=True)
    Config(config_dir='configs', filename='deriv_demo.json', reload=True, root_dir='.', records_dir=record_dir)
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s',
                        filename='logs/deriv.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = ['Volatility 25 Index', 'Volatility 50 Index', 'Volatility 10 Index', 'Volatility 75 Index',
            'Volatility 100 Index', 'Volatility 10 (1s) Index', 'Volatility 25 (1s) Index', 'Volatility 50 (1s) Index',
            'Volatility 75 (1s) Index']
    syms = [ForexSymbol(name=sym) for sym in syms]
    sts = [Strategy(symbol=sym) for sym in syms for Strategy in [FingerFractal, FractalRADI, ADIMACD]]
    bot.add_strategies(sts)
    bot.execute()


if __name__ == '__main__':
    build_bot()