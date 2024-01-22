from aiomql import Bot, Config, FingerTrap
import logging

from src import MFI, RADI, st_closer, AdmiralSymbol, PTrader

Config(config_dir='configs', filename='admiral_1.json', reload=True, root_dir='../')
logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='../logs/admiral.log', datefmt='%Y-%m-%d %H:%M:%S')


def build_bot():
    bot = Bot()
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='NZDUSD-T'), AdmiralSymbol(name='USDCAD-T'),
            AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name="SOLUSD-T")]
    sts = [Strategy(symbol=sym) for sym in syms for Strategy in [MFI, RADI]]
    st1 = [FingerTrap(symbol=sym, trader=PTrader(multiple=True, use_telegram=True, symbol=sym)) for sym in syms]
    bot.add_strategies(sts+st1)
    bot.add_coroutine(st_closer)
    bot.execute()


build_bot()