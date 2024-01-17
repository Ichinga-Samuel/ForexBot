from aiomql import Bot, TimeFrame, Account, Config
import logging

from strategies import ADIMACD2, ADIMACD3, FingerTrap2
from traders import ReverseTrader, RAM
from symbols import AdmiralSymbol

logging.basicConfig(level=logging.INFO)


def build_bot():
    params = {'etf': TimeFrame.M15}
    c = Config(filename='admiral.json', reload=True)
    print(c.filename, c.login)
    bot = Bot()
    fx_symbols = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
                  AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='NZDUSD-T'), AdmiralSymbol(name='USDCAD-T')]
    crypto_symbols = [AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name="SOLUSD-T")]
    st1 = [Strategy(symbol=s, trader=ReverseTrader(symbol=s, ram=RAM(points=100))) for s in fx_symbols for Strategy in [FingerTrap2, ADIMACD3, ADIMACD2]]
    st2 = [Strategy(symbol=s, trader=ReverseTrader(symbol=s, ram=RAM(points=0))) for s in crypto_symbols for Strategy in [FingerTrap2, ADIMACD3, ADIMACD2]]
    st3 = [Strategy(symbol=s, trader=ReverseTrader(symbol=s, ram=RAM(points=100)), params=params) for s in fx_symbols for Strategy in [ADIMACD3, ADIMACD2]]
    st4 = [Strategy(symbol=s, trader=ReverseTrader(symbol=s, ram=RAM(points=0)), params=params) for s in crypto_symbols for Strategy in [ADIMACD3, ADIMACD2]]

    bot.add_strategies(st1 + st2 + st3 + st4)
    bot.execute()


build_bot()