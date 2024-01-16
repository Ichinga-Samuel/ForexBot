from logging import getLogger
import asyncio
from dataclasses import dataclass

from aiomql import Symbol, Candles, Strategy, TimeFrame, Sessions, OrderType, Tracker as Tracker_, SimpleTrader, Trader

logger = getLogger(__name__)


@dataclass
class Tracker(Tracker_):
    sl: float = 0


class RADI(Strategy):
    tracker: Tracker
    ecc: int
    tcc: int
    ttf: TimeFrame
    etf: TimeFrame
    first_sma: int
    second_sma: int
    third_sma: int
    rsi_period: int
    rsi_sma: int
    trend: int = 2
    _parameters = {"ecc": 576, "tcc": 48, "ttf": TimeFrame.H1, "etf": TimeFrame.M15, 'second_sma': 9, 'first_sma': 5,
                   'third_sma': 15, 'rsi_period': 9, 'rsi_sma': 20}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None,
                 name: str = 'RADI', trader: Trader = None):
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
            if all((c.caf and c.fas and c.sat) for c in trend):
                self.tracker.update(trend="bullish")

            elif all(c.cbf and c.fbs and c.sbt for c in trend):
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
            candles.ta.ad(volume="tick_volume", append=True)
            candles.ta.rsi(close="AD", length=self.rsi_period, append=True)
            candles.rename(**{f'RSI_{self.rsi_period}': 'rsi'})
            candles.ta.sma(close='rsi', length=self.rsi_sma, append=True)
            candles.rename(**{f'SMA_{self.rsi_sma}': 'rsi_sma'})
            above = candles.ta_lib.cross(candles["rsi"], candles["rsi_sma"])
            below = candles.ta_lib.cross(candles["rsi"], candles["rsi_sma"], above=False)
            rsi = candles[-1].rsi

            if self.tracker.bullish and rsi < 70 and above.iloc[-2]:
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY)
            elif self.tracker.bearish and rsi > 30 and below.iloc[-2]:
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(trend="ranging")

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