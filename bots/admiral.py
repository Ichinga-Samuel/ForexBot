from aiomql import Bot, Config
import logging

from src import FingerFractal, FractalRADI, ADIMACD, AdmiralSymbol

Config(config_dir='configs', filename='admiral.json', reload=True, root_dir='.')

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log', datefmt='%Y-%m-%d %H:%M:%S')


def build_bot():
    bot = Bot()
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='NZDUSD-T'), AdmiralSymbol(name='USDCAD-T'),
            AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name="SOLUSD-T")]
    sts = [Strategy(symbol=sym) for sym in syms for Strategy in [FingerFractal, FractalRADI, ADIMACD]]
    bot.add_strategies(sts)
    bot.execute()


build_bot()