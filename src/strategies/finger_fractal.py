from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.adx_closer import adx_closer
from ..traders.b_trader import BTrader

logger = getLogger(__name__)


class FingerFractal(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M15
    timeout: int = 7200
    parameters = {"first_ema": 10, "second_ema": 21, "third_ema": 50, "ttf": TimeFrame.H4, "tcc": 720}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'FingerFractal'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or BTrader(symbol=self.symbol, track_trades=False)
        self.tracker: Tracker = Tracker(snooze=self.ttf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current, order_type=None)
            candles.ta.ema(length=self.first_ema, append=True)
            candles.ta.ema(length=self.second_ema, append=True)
            candles.ta.ema(length=self.third_ema, append=True)
            candles.ta.adx(append=True)
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"EMA_{self.third_ema}": "third",
                                            "ADX_14": "adx", "DMP_14": "dmp", "DMN_14": "dmn"})

            candles['cas'] = candles.ta_lib.above(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['sat'] = candles.ta_lib.above(candles.second, candles.third)

            candles['cbs'] = candles.ta_lib.below(candles.close, candles.first)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles['sbt'] = candles.ta_lib.below(candles.second, candles.third)
            current = candles[-1]
            prev = candles[-2]

            if (current.is_bullish() and prev.dmp < current.dmp > current.dmn and current.adx >= 25 and
                all([current.cas, current.fas, current.sat])):
                self.tracker.update(snooze=TimeFrame.H1.time, order_type=OrderType.BUY)

            elif (current.is_bearish() and prev.dmn < current.dmn > current.dmp and
                  all([current.cbs, current.fbs, current.sbt])):
                self.tracker.update(snooze=TimeFrame.H1.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            # await self.sleep(self.tracker.snooze)
            while True:
                await sess.check()
                try:
                    await self.check_trend()
                    if not self.tracker.new:
                        await asyncio.sleep(2)
                        continue
                    if self.tracker.order_type is None:
                        await self.sleep(self.tracker.snooze)
                        continue
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters)
                    await asyncio.sleep(self.timeout)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
