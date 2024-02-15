from logging import getLogger
import asyncio
import warnings

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader
from aiomql.utils import find_bearish_fractal, find_bullish_fractal

from ..utils.tracker import Tracker
from ..utils.ram import RAM
from ..closers.ema_rsi_closer import ema_rsi_closer
from ..traders.sp_trader import SPTrader

logger = getLogger(__name__)


class FractalRADI(Strategy):
    tracker: Tracker
    ecc: int
    tcc: int
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    mfi_ema: int
    parameters = {"ecc": 2880, "tcc": 720, "ttf": TimeFrame.H6, "etf": TimeFrame.M30, 'second_ema': 21, 'first_ema': 13,
                  'third_ema': 34, 'mfi_ema': 34, 'closer': ema_rsi_closer}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None,
                 name: str = 'FractalRADI', trader: Trader = None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or SPTrader(symbol=self.symbol, track_trades=True, ram=RAM(risk_to_reward=5))

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
            candles.rename(**{f'EMA_{self.first_ema}': 'first_ema', f'EMA_{self.second_ema}': 'second_ema',
                              f'EMA_{self.third_ema}': 'third_ema'})
            candles['caf'] = candles.ta_lib.above(candles.close, candles.first_ema)
            candles["fas"] = candles.ta_lib.above(candles.first_ema, candles.second_ema)
            candles['sat'] = candles.ta_lib.above(candles.second_ema, candles.third_ema)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first_ema)
            candles["fbs"] = candles.ta_lib.below(candles.first_ema, candles.second_ema)
            candles['sbt'] = candles.ta_lib.below(candles.second_ema, candles.third_ema)
            trend = candles[-2:]
            if all(c.caf and c.fas and c.sat for c in trend) and trend[-2].is_bullish():
                self.tracker.update(trend="bullish")

            elif all(c.cbf and c.fbs and c.sbt for c in trend) and trend[-2].is_bearish():
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging", snooze=self.ttf.time, order_type=None)
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
            warnings.filterwarnings("ignore")
            candles.ta.mfi(volume='tick_volume', append=True)
            candles.rename(**{'MFI_14': 'mfi'})
            candles.ta.ema(close='mfi', length=self.mfi_ema, append=True)
            candles.rename(**{f'EMA_{self.mfi_ema}': 'ema'})
            above = candles.ta_lib.cross(candles.mfi, candles.ema)
            below = candles.ta_lib.cross(candles.mfi, candles.ema, above=False)
            if self.tracker.bullish and above.iloc[-1]:
                sl = find_bullish_fractal(candles).low
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl)
            elif self.tracker.bearish and below.iloc[-1]:
                sl = find_bearish_fractal(candles).high
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
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(3600)
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
