import asyncio
from pprint import pprint as pp
import pandas
import pandas_ta as ta
from aiomql import Candle, Candles, Account, Symbol, TimeFrame, OrderType, Order, RAM, ForexSymbol, Positions


async def check():
    async with Account() as acc:
        pp(acc.symbols)
        # sym = ForexSymbol(name="BTCUSD")
        # await sym.init()
        # candles = await sym.copy_rates_from_pos(timeframe=TimeFrame.M5, count=100)
        # candles.ta.atr(length=12, append=True)
        # candles.ta.ad(volume='tick_volume', append=True)
        # candles.rename(AD='ad')
        # print(candles[-1]['AD'])
        # # candles.ta.rsi(close='ad', append=True)
        # # candles.rename(RSI_14='rsi')
        # # ta.sma
        # candles.ta.atr()
        # print(candles.Index)


# class GO:
#     def __init__(self):
#         self.man = 'woman'
#
#     def __getitem__(self, item):
#         return self.__dict__[item]


# v = GO()
# # v.girl = 'boy'
# print(v['girl'])


asyncio.run(check())