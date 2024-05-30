from src.bots import crypto, derived, derived_2, deriv_scalper
from aiomql import Bot


if __name__ == '__main__':
    Bot.run_bots(funcs={derived: {}, derived_2: {}, crypto: {}, deriv_scalper: {}})
