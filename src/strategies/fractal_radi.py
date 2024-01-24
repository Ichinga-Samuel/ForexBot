from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.patterns import find_bearish_fractal, find_bullish_fractal
from ..traders.sl_trader import SLTrader

logger = getLogger(__name__)


class FractalRADI(Strategy):
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
    parameters = {"ecc": 192, "tcc": 48, "ttf": TimeFrame.H1, "etf": TimeFrame.M15, 'second_sma': 9, 'first_sma': 5,
                   'third_sma': 15, 'rsi_period': 9, 'rsi_sma': 20, 'used_fractal': True}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None,
                 name: str = 'FractalRADI', trader: Trader = None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or SLTrader(symbol=self.symbol, multiple=False, use_telegram=True)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
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
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.ttf.time, order_type=None)

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
                sl = find_bullish_fractal(candles)
                self.parameters['used_fractal'] = True if sl is not None else False
                sl = sl.low if sl is not None else candles[-12: -1].low.min()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl)
            elif self.tracker.bearish and rsi > 30 and below.iloc[-2]:
                sl = find_bearish_fractal(candles)
                self.parameters['used_fractal'] = True if sl is not None else False
                sl = sl.high if sl is not None else candles[-12: -1].high.max()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL, sl=sl)
            else:
                self.tracker.update(trend="ranging", order_type=None)

        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.confirm_trend\n")
            self.tracker.update(snooze=self.etf.time, order_type=None)

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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters,
                                                  sl=self.tracker.sl)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} For {self.symbol} in {self.__class__.__name__}.trade\n")
                    await self.sleep(self.ttf.time)