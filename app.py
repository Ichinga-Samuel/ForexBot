from src.bots import deriv1, admiral, admiral1, deriv, test_bot
from aiomql import Bot


if __name__ == '__main__':
    Bot.run_bots(bots={deriv1: {}, admiral1: {}, deriv: {}})
