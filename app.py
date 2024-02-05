from bots import deriv1, admiral, admiral1
from aiomql import Bot


if __name__ == '__main__':
    Bot.run_bots(bots={deriv1: {}, admiral: {}, admiral1: {}})