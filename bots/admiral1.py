import logging

from aiomql import Bot, Config, FingerTrap

from src import RADI, FingerFractal, AdmiralSymbol, PTrader, RAM


def build_bot():
    Config(config_dir='configs', filename='admiral_1.json', reload=True, records_dir='records/admiral1')
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(message)s', filename='logs/admiral.log', datefmt='%Y-%m-%d %H:%M:%S')
    bot = Bot()
    ram = RAM(risk_to_reward=1.5, points=50)
    syms = [AdmiralSymbol(name='EURUSD-T'), AdmiralSymbol(name='GBPUSD-T'), AdmiralSymbol(name='USDJPY-T'),
            AdmiralSymbol(name='AUDUSD-T'), AdmiralSymbol(name='NZDUSD-T'), AdmiralSymbol(name='USDCAD-T'),
            AdmiralSymbol(name='BTCUSD-T'), AdmiralSymbol(name='ETHUSD-T'), AdmiralSymbol(name="SOLUSD-T")]
    sts = [Strategy(symbol=sym, trader=PTrader(symbol=sym, ram=ram)) for sym in syms for Strategy in [RADI, FingerTrap]]
    bot.add_strategies(sts)
    bot.execute()


if __name__ == '__main__':
    build_bot()