from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader
from aiomql.utils import find_bearish_fractal, find_bullish_fractal

from ..utils.tracker import Tracker
from ..closers.ema_closer import ema_closer
from ..traders.p_trader import PTrader
from ..utils.ram import RAM

logger = getLogger(__name__)


class NFF(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    entry_ema: int
    tcc: int
    ecc: int
    trader: Trader
    tracker: Tracker
    parameters: dict
    interval: TimeFrame = TimeFrame.M30

    parameters = {"first_ema": 5, "second_ema": 8, "third_ema": 13, "ttf": TimeFrame.H4, "tcc": 720,
                  'closer': ema_closer, "etf": TimeFrame.M30, 'ecc': 4000, 'entry_ema': 5}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'NFF'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or PTrader(symbol=self.symbol, ram=RAM(risk_to_reward=3),
                                        trail_profits={'trail_start': 0.375})
        self.tracker: Tracker = Tracker(snooze=self.interval.time)

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
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"EMA_{self.third_ema}": "third"})

            candles['caf'] = candles.ta_lib.above(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['sat'] = candles.ta_lib.above(candles.second, candles.third)

            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles['sbt'] = candles.ta_lib.below(candles.second, candles.third)
            current = candles[-1]

            if current.is_bullish() and all([current.fas, current.sat, current.caf]):
                self.tracker.update(trend="bullish")

            elif current.is_bearish() and all([current.fbs, current.sbt, current.cbf]):
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) > self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, entry_time=current, order_type=None)

            candles.ta.ema(length=self.entry_ema, append=True)
            candles.rename(inplace=True, **{f"EMA_{self.entry_ema}": "ema"})
            candles['cae'] = candles.ta_lib.cross(candles.close, candles.ema, above=True)
            candles['cbe'] = candles.ta_lib.cross(candles.close, candles.ema, above=False)
            current = candles[-1]

            if self.tracker.bullish and current.cae:
                self.tracker.update(order_type=OrderType.BUY, snooze=self.ttf.time)

            elif self.tracker.bearish and current.cbe:
                self.tracker.update(order_type=OrderType.SELL, snooze=self.ttf.time)
            else:
                self.tracker.update(snooze=self.etf.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.confirm_trend")
            self.tracker.update(snooze=self.etf.time, order_type=None)

    async def watch_market(self):
        await self.check_trend()
        if not self.tracker.ranging:
            await self.confirm_trend()

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.tracker.snooze)
            while True:
                await sess.check()
                try:
                    await self.watch_market()
                    if not self.tracker.new:
                        await asyncio.sleep(2)
                        continue
                    if self.tracker.order_type is None:
                        await self.sleep(self.tracker.snooze)
                        continue
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
