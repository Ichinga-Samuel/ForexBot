from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..traders.sp_trader import SPTrader

logger = getLogger(__name__)


class FingerFractal(Strategy):
    ttf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    first_sl: float
    second_sl: float
    parameters = {"first_ema": 5, "second_ema": 8, "third_ema": 13, "ttf": TimeFrame.H1, "tcc": 168}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'FingerFractal'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or SPTrader(symbol=self.symbol, multiple=True, risk_to_rewards=[2, 2, 2])
        self.tracker: Tracker = Tracker(snooze=self.ttf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.ema(length=self.first_ema, append=True)
            candles.ta.ema(length=self.second_ema, append=True)
            candles.ta.ema(length=self.third_ema, append=True)
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"EMA_{self.third_ema}": "third"})

            candles['caf'] = candles.ta_lib.above(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['sat'] = candles.ta_lib.above(candles.second, candles.third)

            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles['sbt'] = candles.ta_lib.below(candles.second, candles.third)
            trend = candles[-2:]
            current = candles[-1]
            if candles[-2].is_bullish() and all([current.caf, current.fas, current.sat]):
                sl = trend.low.min()
                self.tracker.update(sl=sl, snooze=self.ttf, order_type=OrderType.BUY)

            elif candles[-2].is_bearish() and all([current.cbf, current.fbs, current.sbt]):
                sl = trend.high.max()
                self.tracker.update(snooze=self.ttf, order_type=OrderType.SELL, sl=sl)
            else:
                self.tracker.update(trend="ranging", snooze=self.ttf.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend\n")
            self.tracker.update(snooze=self.ttf.time, order_type=None)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.ttf.time)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters,
                                                  sl=self.tracker.sl)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade\n")
                    await self.sleep(self.trend_time_frame.time)