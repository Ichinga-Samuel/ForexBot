import logging
from pathlib import Path

from aiomql import Bot, Config, FingerTrap, TimeFrame

from src import MFI, RADI, AdmiralSymbol, PTrader


def build_bot():
    params = {'ttf': TimeFrame.M5, 'etf': TimeFrame.M1}
    record_dir = Path.cwd() / 'records' / 'admiral1'
    record_dir.mkdir(parents=True, exist_ok=True)
    Config(config_dir='configs', filename='admiral_1.json', reload=True, root_dir='.', records_dir=record_dir)
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='NZDUSD-T'), AdmiralSymbol(name='USDCAD-T'),
            AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name="SOLUSD-T")]
    sts = [Strategy(symbol=sym) for sym in syms for Strategy in [MFI, RADI]]
    st1 = [FingerTrap(symbol=sym, params=params, trader=PTrader(multiple=True, use_telegram=True, symbol=sym)) for sym in syms]
    bot.add_strategies(sts+st1)
    bot.execute()


if __name__ == '__main__':
    build_bot()