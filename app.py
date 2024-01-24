from bots import deriv, deriv1, admiral, admiral1
from aiomql import Bot


if __name__ == '__main__':
    Bot.run_bots(bots={deriv: {}, deriv1: {}, admiral: {}, admiral1: {}})