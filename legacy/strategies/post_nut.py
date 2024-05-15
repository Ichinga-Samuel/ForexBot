import asyncio
import time
import warnings

from aiomql import Strategy, TimeFrame, Sessions, Trader, Symbol, OrderType
from aiomql.utils import find_bearish_fractal, find_bullish_fractal
from logging import getLogger

from ..utils.find_fractals import find_bearish_fractals, find_bullish_fractals
from ..utils.patterns import is_half_bearish_fractal, is_half_bullish_fractal
# from ..traders.pn_trader import PNTrader
from ..traders.p_trader import PTrader
from ..utils.tracker import Tracker
from ..utils.ram import RAM
from ..closers import ema_closer

logger = getLogger(__name__)


class PostNut(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    tcc: int
    ecc: int
    first_sma: int
    second_sma: int
    third_sma: int
    fourth_sma: int
    mfi_length: int
    trader: Trader
    tracker: Tracker
    trend: int
    interval: int = 180
    parameters = {"ttf": TimeFrame.M15, "etf": TimeFrame.M15, "tcc": 720, "ecc": 4320, "first_sma": 5, "second_sma": 9,
                  "mfi_length": 14, "third_sma": 2, 'fourth_sma': 15, 'interval': 180, 'closer': ema_closer,
                  'cap': 5, 'ntr': True}

    def __init__(self, *, symbol: Symbol, trader: Trader = None, sessions: Sessions = None, name: str = 'PostNut'):
        super().__init__(symbol=symbol, sessions=sessions, name=name)
        # ram = RAM(risk=0.01, min_amount=3, max_amount=3, loss_limit=4, use_ram=True)
        # self.trader = trader or SPTrader(symbol=self.symbol, ram=ram, multiple=True, risk_to_rewards=[2, 2.5, 3])
        self.trader = trader or PTrader(symbol=self.symbol, ram=RAM(risk_to_reward=6), trail_profits={'trail_start': 0.50})
        self.tracker: Tracker = Tracker(snooze=self.ttf.time)

    async def first_entry(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.sma(length=self.first_sma, append=True)
            candles.ta.sma(length=self.second_sma, append=True)
            candles.ta.sma(length=self.third_sma, append=True)
            warnings.filterwarnings("ignore")
            candles.ta.mfi(length=self.mfi_length, volume='tick_volume',  append=True)
            candles.rename(inplace=True, **{f"SMA_{self.first_sma}": "first", f"SMA_{self.second_sma}": "second",
                                            f"MFI_{self.mfi_length}": "mfi", f"SMA_{self.third_sma}": "third"})
            candles['caf'] = candles.ta_lib.above(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['cat'] = candles.ta_lib.cross(candles.close, candles.third)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles['cbt'] = candles.ta_lib.cross(candles.close, candles.third, above=False)

            current = candles[-1]
            bullish_fractals = find_bullish_fractals(candles, count=2)
            bearish_fractals = find_bearish_fractals(candles, count=2)
            if current.caf and current.fas:
                first, second = bearish_fractals[0], bearish_fractals[1]
                if first.middle.mfi > second.middle.mfi:
                    if is_half_bullish_fractal(candles):
                        wait = (t := time.time()) % self.ttf.time
                        wait = (self.ttf.time - wait) + t
                        self.tracker.update(trend="bullish", wait=wait)
                        while time.time() < self.tracker.wait:
                            cans = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
                            cans.ta.sma(length=self.third_sma, append=True)
                            cans.rename(inplace=True, **{f"SMA_{self.third_sma}": "third"})
                            cans['cat'] = cans.ta_lib.cross(cans.close, cans.third)
                            current = cans[-1]
                            if current.cat:
                                sl = bullish_fractals[0].middle.low
                                volume = self.symbol.volume_min * 4
                                await self.trader.place_trade(order_type=OrderType.BUY, sl=sl,
                                                              parameters=self.parameters)
                                wait = (t := time.time()) % self.ttf.time
                                wait = (self.ttf.time - wait) + t
                                self.tracker.update(trend="bullish", wait=wait)
                                break
                            else:
                                await asyncio.sleep(self.interval)
                                continue
                        self.tracker.update(snooze=self.ttf.time, trend='ranging')
            elif current.cbf and current.fbs:
                first, second = bullish_fractals[0], bullish_fractals[1]
                if first.middle.mfi < second.middle.mfi:
                    if is_half_bearish_fractal(candles):
                        wait = (t := time.time()) % self.ttf.time
                        wait = (self.ttf.time - wait) + t
                        self.tracker.update(trend="bearish", wait=wait)
                        while time.time() < self.tracker.wait:
                            cans = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
                            cans.ta.sma(length=self.third_sma, append=True)
                            cans.rename(inplace=True, **{f"SMA_{self.third_sma}": "third"})
                            cans['cbt'] = cans.ta_lib.cross(cans.close, cans.third, above=False)
                            current = cans[-1]
                            if current.cbt:
                                sl = bearish_fractals[0].middle.high
                                volume = self.symbol.volume_min * 4
                                await self.trader.place_trade(order_type=OrderType.SELL, sl=sl,
                                                              parameters=self.parameters)
                                wait = (t := time.time()) % self.ttf.time
                                wait = (self.ttf.time - wait) + t
                                self.tracker.update(trend="bearish", wait=wait)
                                break
                            else:
                                await asyncio.sleep(self.interval)
                                continue
                        self.tracker.update(snooze=self.ttf.time, trend='ranging')
            else:
                self.tracker.update(snooze=self.ttf.time, trend='ranging')

        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.first_entry")
            await self.sleep(self.ttf.time)

    async def second_entry(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, entry_time=current)
            candles.ta.stoch(append=True)
            candles.rename(inplace=True, **{"STOCHk_14_3_3": "stochk", "STOCHd_14_3_3": "stochd"})
            if self.tracker.bullish:
                candles['cas'] = candles.ta_lib.cross_value(candles.stochk, 35)
                current = candles[-1]
                if current.cas:
                    sl = find_bullish_fractal(candles).low
                    await self.trader.place_trade(order_type=OrderType.BUY, sl=sl, parameters=self.parameters)
                    self.tracker.update(snooze=self.etf.time)
            elif self.tracker.bearish:
                current = candles[-1]
                candles['cbs'] = candles.ta_lib.cross_value(candles.stochk, 70, above=False)
                if current.cbs:
                    sl = find_bearish_fractal(candles).high
                    await self.trader.place_trade(order_type=OrderType.SELL, sl=sl, parameters=self.parameters)
                    self.tracker.update(snooze=self.etf.time)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.second_entry")
            await self.sleep(self.ttf.time)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}-l")
        async with self.sessions as sess:
            await self.sleep(self.etf.time)
            while True:
                await sess.check()
                try:
                    await self.first_entry()
                    if not self.tracker.new:
                        await asyncio.sleep(2)
                        continue
                    if not self.tracker.ranging:
                        while time.time() < self.tracker.wait:
                            await self.second_entry()
                            if not self.tracker.new:
                                await asyncio.sleep(2)
                                continue
                            await self.sleep(self.etf.time)
                    await self.sleep(self.ttf.time)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade\n")
                    await self.sleep(self.etf.time)
