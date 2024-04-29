from src.bots import crypto, derived, derived_2
from aiomql import Bot


if __name__ == '__main__':
    Bot.run_bots(bots={crypto: {}, derived: {}, derived_2: {}})
