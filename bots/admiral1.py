import logging

from aiomql import Bot, Config

from src import FractalRADI, FingerFractal, FractalADIMACD, FractalMFI, AdmiralSymbol


def build_bot():
    Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral1')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='NZDUSD-T'), AdmiralSymbol(name='USDCAD-T'),
            AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name="SOLUSD-T")]
    sts = [Strategy(symbol=sym) for sym in syms for Strategy in [FractalRADI, FingerFractal, FractalADIMACD, FractalMFI]]
    bot.add_strategies(sts)
    bot.execute()