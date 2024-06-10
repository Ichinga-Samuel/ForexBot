from src.bots import crypto, deriv1, deriv2, deriv_scalper
from aiomql import Bot


if __name__ == '__main__':
    Bot.run_bots(funcs={deriv_scalper: {}, deriv2: {}, deriv1: {}, crypto: {}})
