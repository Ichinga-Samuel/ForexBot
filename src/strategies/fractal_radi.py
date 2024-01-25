from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.ram import RAM
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
    mfi_sma: int
    parameters = {"ecc": 576, "tcc": 48, "ttf": TimeFrame.H1, "etf": TimeFrame.M15, 'second_sma': 15, 'first_sma': 5,
                  'mfi_sma': 15}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None,
                 name: str = 'FractalRADI', trader: Trader = None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or SLTrader(symbol=self.symbol, multiple=False, use_telegram=True, ram=RAM(risk_to_reward=1))

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return

            self.tracker.update(new=True, trend_time=current)
            candles.ta.sma(length=self.first_sma, append=True)
            candles.ta.sma(length=self.second_sma, append=True)
            candles.rename(**{f'SMA_{self.first_sma}': 'first_sma', f'SMA_{self.second_sma}': 'second_sma'})

            candles['caf'] = candles.ta_lib.above(candles.close, candles.first_sma)
            candles["fas"] = candles.ta_lib.above(candles.first_sma, candles.second_sma)

            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first_sma)
            candles["fbs"] = candles.ta_lib.below(candles.first_sma, candles.second_sma)

            trend = candles[-3: -1]
            if all((c.caf and c.fas) for c in trend):
                self.tracker.update(trend="bullish")

            elif all(c.cbf and c.fbs for c in trend):
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
            candles.ta.mfi(volume='tick_volume', append=True, length=9)
            candles.rename(**{'MFI_9': 'mfi'})
            candles.ta.sma(close='mfi', length=self.mfi_sma, append=True)
            candles.rename(**{f'SMA_{self.mfi_sma}': 'sma'})
            above = candles.ta_lib.cross(candles.mfi, candles.sma)
            below = candles.ta_lib.cross(candles.mfi, candles.sma, above=False)
            trend = candles[-4: -1]
            if self.tracker.bullish and above.iloc[-2]:
                sl = trend.low.min()
                self.parameters['used_fractal'] = False
                # sl = find_bullish_fractal(candles)
                # self.parameters['used_fractal'] = True if sl is not None else False
                # sl = sl.low if sl is not None else candles[-12: -1].low.min()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl)
            elif self.tracker.bearish and below.iloc[-2]:
                sl = trend.high.max()
                self.parameters['used_fractal'] = False
                # sl = find_bearish_fractal(candles)
                # self.parameters['used_fractal'] = True if sl is not None else False
                # sl = sl.high if sl is not None else candles[-12: -1].high.max()
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