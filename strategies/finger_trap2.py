from logging import getLogger
import asyncio
from dataclasses import dataclass

from aiomql import Symbol, Candles, Strategy, TimeFrame, Sessions, OrderType, Tracker as Tracker_, SimpleTrader, Trader
from pandas_ta import sma

logger = getLogger(__name__)


@dataclass
class Tracker(Tracker_):
    sl: float = 0


class FingerTrap2(Strategy):
    tracker: Tracker
    ecc: int
    tcc: int
    ttf: TimeFrame
    etf: TimeFrame
    first_sma: int
    second_sma: int
    third_sma: int
    trend: int = 3
    _parameters = {"ecc": 576, "tcc": 48, "ttf": TimeFrame.H1, "etf": TimeFrame.M5, 'second_sma': 20, 'first_sma': 8,
                   'third_sma': 32}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None,
                 name: str = 'FingerTrap2', trader: Trader = None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or SimpleTrader(symbol=self.symbol)

    async def check_trend(self):
        try:
            candles: Candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.new = False
                return

            self.tracker.update(new=True, trend_time=current)
            candles.ta.sma(length=self.first_sma, append=True)
            candles.ta.sma(length=self.second_sma, append=True)
            candles.ta.sma(length=self.third_sma, append=True)
            candles.rename(**{f'SMA_{self.first_sma}': 'first_sma', f'SMA_{self.second_sma}': 'second_sma',
                              f'SMA_{self.third_sma}': 'third_sma'})

            candles['caf'] = candles.ta_lib.above(candles.close, candles.first_sma)
            candles["fas"] = candles.ta_lib.above(candles.first_sma, candles.second_sma)
            candles["sat"] = candles.ta_lib.above(candles.second_sma, candles.third_sma)

            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first_sma)
            candles["fbs"] = candles.ta_lib.below(candles.first_sma, candles.second_sma)
            candles["sbt"] = candles.ta_lib.below(candles.second_sma, candles.third_sma)

            trend = candles[-self.trend-1: -1]
            current = candles[-1]
            if current.is_bullish() and all((c.caf and c.fas and c.sat) for c in trend):
                self.tracker.update(trend="bullish")

            elif current.is_bearish() and all(c.cbf and c.fbs and c.sbt for c in trend):
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging", snooze=self.ttf.time)
        except Exception as err:
            logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.check_trend")
            return

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.new = False
                return
            self.tracker.update(new=True, entry_time=current)
            candles.ta.macd(append=True, fillna=0)
            candles.rename(inplace=True, **{f"MACD_12_26_9": "macd", f"MACDh_12_26_9": "macdh",
                                            f"MACDs_12_26_9": "macds"})
            above = candles.ta_lib.cross(candles["macd"], candles["macds"])
            below = candles.ta_lib.cross(candles["macd"], candles["macds"], above=False)
            if self.tracker.bullish and above.iloc[-2]:
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY)
            elif self.tracker.bearish and below.iloc[-2]:
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(snooze=self.etf.time, order_type=None)
        except Exception as err:
            logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.confirm_trend")
            return

    async def watch_market(self):
        await self.check_trend()
        if not self.tracker.ranging:
            await self.confirm_trend()

    async def trade(self):
        logger.info(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.etf.time)
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
                    self.tracker.order_type = None
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.trend_time_frame.time)
                    continue