import logging

from aiomql import Bot, Config

from src import ADIMACD, MFI, RADI, AdmiralSymbol, points_closer


def build_bot():
    Config(config_dir='configs', filename='admiral.json', reload=True, records_dir='records/admiral')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log',
                        datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='NZDUSD-T'), AdmiralSymbol(name='USDCAD-T'),
            AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name="SOLUSD-T")]
    sts = [Strategy(symbol=sym) for sym in syms for Strategy in [ADIMACD, MFI, RADI]]
    bot.add_strategies(sts)
    bot.add_coroutine(points_closer)
    bot.execute()