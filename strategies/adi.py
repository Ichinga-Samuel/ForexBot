# import asyncio
#
# from aiomql import Strategy, Symbol, TimeFrame, Candles, Candle, OrderType
#  import DealTrader
#
#
# class ADICandle(Candle):
#     def __init__(self, **kwargs):
#         self.fast_sma: float = kwargs.pop('fast_sma')
#         self.slow_sma: float = kwargs.pop('slow_sma')
#         self.ad: float = kwargs.pop('ad')
#         self.volume: float = kwargs.get('volume')
#         super().__init__(**kwargs)
# class ADIStrategy(Strategy):
#     candles: Candles
#     current: ADICandle
#     name = 'ADI Strategy'
#     candle_class = ADICandle
#     def __init__(self, symbol: Symbol, params: dict | None = None):
#         super().__init__(symbol=symbol, params=params)
#         self.timeframe = self.parameters.setdefault('timeframe', TimeFrame.H1)
#         self.fast_sma = self.parameters.setdefault('fast_sma', 8)
#         self.slow_sma = self.parameters.setdefault('slow_sma', 13)
#         self.trader = DealTrader(symbol=self.symbol)
#
#     async def get_data(self):
#         bars = await self.symbol.copy_rates_from_pos(timeframe=self.timeframe)
#         await asyncio.to_thread(bars.ta.ad, append=True, volume='tick_volume')
#         task2 = asyncio.to_thread(bars.ta.sma, length=self.fast_sma, append=True, close='AD')
#         task3 = asyncio.to_thread(bars.ta.sma, length=self.slow_sma, append=True, close='AD')
#         await asyncio.gather(task2, task3)
#         bars.rename(columns={f'SMA_{self.fast_sma}': 'fast_sma', f'SMA_{self.slow_sma}': 'slow_sma',
#                              'AD': 'ad'}, inplace=True)
#         self.candles = self.candles_class(data=bars, candle_class=self.candle_class)
#         self.current = self.candles[-1]
#
#     async def find_fractal(self, trend='bullish'):
#         fractals = self.candles[-3: -1]
#         if trend == 'bullish':
#             if fractals[0].low > fractals[1].low > fractals[2].low:
#                 return True
#         if trend == 'bearish':
#             if fractals[0].high < fractals[1].high < fractals[2].high:
#                 return True
#         return False
#
#     async def check_trend(self):
#         if self.current.fast_sma > self.current.slow_sma:
#             return 'bullish'
#         if self.current.fast_sma < self.current.slow_sma:
#             return 'bearish'
#
#     async def watch_market(self):
#         await self.get_data()
#         trend = await self.check_trend()
#         enter = await self.find_fractal(trend=trend)
#         if not enter:
#             return 'wait'
#
#         if trend == 'bullish':
#             if self.current.low < self.candles[-2].low:
#                 return 'buy'
#             return 'check again'
#
#         if trend == 'bearish':
#             if self.current.high > self.candles[-2].high:
#                 return 'sell'
#             return 'check again'
#
#     async def trade(self):
#         try:
#             print(f'Trading strategy {self.name} on {self.symbol.name}')
#             while True:
#                 res = await self.watch_market()
#                 if res == 'wait':
#                     await self.sleep(self.timeframe.time)
#                 if res == 'check again':
#                     await self.sleep(self.timeframe.time / 10)
#                 if res == 'buy':
#                     await self.trader.place_trade(order=OrderType.BUY, points=50, params=self.parameters)
#                 if res == 'sell':
#                     await self.trader.place_trade(order=OrderType.SELL, points=50, params=self.parameters)
#                 await self.sleep(self.timeframe.time)
#         except Exception as exe:
#             print(exe)
#
