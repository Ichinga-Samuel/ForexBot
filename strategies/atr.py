from logging import getLogger
import asyncio

from aiomql import Symbol, Candles, Strategy, TimeFrame, Sessions, OrderType, Tracker

logger = getLogger(__name__)


class ATR(Strategy):
    tracker: Tracker
    ecc: int
    tcc: int
    ttf: TimeFrame
    etf: TimeFrame
    slow_sma: int
    fast_sma: int
    rsi_period: int
    rsi_upper: int
    atr_period: int
    _parameters = {"ecc": 288, "tcc": 24, "ttf": TimeFrame.H1, "etf": TimeFrame.M5, 'slow_sma': 20, 'fast_sma': 5,
                   'rsi_period': 14, 'rsi_upper': 60, 'atr_period': 14}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None, name: str = "ATRStrategy"):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)

    async def check_trend(self):
        try:
            candles: Candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.new = False
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.atr(length=self.atr_period, append=True)
            candles.rename(**{f'ATRr_{self.atr_period}': 'atr'})
            candles.ta.rsi(close="atr", append=True)
            candles.rename(**{f'RSI_{self.rsi_period}': 'rsi'})
            rsi = candles[-2]['rsi']
            if rsi >= self.rsi_upper:
                candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
                if not candles[-1].time >= self.tracker.trend_time:
                    self.tracker.new = False
                    return
                candles.ta.sma(length=self.fast_sma, append=True)
                candles.ta.sma(length=self.slow_sma, append=True)
                candles.rename(**{f'SMA_{self.fast_sma}': 'fast_sma', f'SMA_{self.slow_sma}': 'slow_sma'})
                above = candles.ta_lib.cross(candles["fast_sma"], candles["slow_sma"])
                below = candles.ta_lib.cross(candles["fast_sma"], candles["slow_sma"], above=False)
                if above[-2]["fast_smaXA_slow_sma"]:
                    self.tracker.update(order=OrderType.BUY, snooze=self.etf.time)
                elif below[-2]["fast_smaXB_slow_sma"]:
                    self.tracker.update(order=OrderType.SELL, snooze=self.etf.time)
                else:
                    self.tracker.update(order=None, snooze=self.etf.time)
            else:
                self.tracker.update(order=None, snooze=self.ttf.time)
        except Exception as err:
            logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.check_trend")
            return

    async def trade(self):
        logger.info(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            while True:
                await sess.check()
                try:
                    await self.check_trend()
                    if not self.tracker.new:
                        await asyncio.sleep(2)
                        continue
                    if self.tracker.order is None:
                        await self.sleep(self.tracker.snooze)
                        continue
                    await self.trader.place_trade(order_type=self.tracker.order, parameters=self.parameters)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.trend_time_frame.time)
                    continue