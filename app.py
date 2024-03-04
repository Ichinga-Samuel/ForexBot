from src.bots import deriv1, admiral, admiral1, deriv
from aiomql import Bot


if __name__ == '__main__':
    Bot.run_bots(bots={deriv: {}, deriv1: {}, admiral: {}, admiral1: {}})
