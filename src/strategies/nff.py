from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.ema_closer import ema_closer
from ..traders.p_trader import PTrader

logger = getLogger(__name__)


class NFF(Strategy):
    ftf: TimeFrame
    stf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    fourth_ema: int
    entry_ema: int
    fcc: int
    scc: int
    ecc: int
    trader: Trader
    tracker: Tracker
    parameters: dict
    interval: TimeFrame = TimeFrame.H1

    parameters = {"third_ema": 21, "first_ema": 55, "second_ema": 21, "fourth_ema": 8, "ftf": TimeFrame.H4, "fcc": 720,
                  "scc": 2880, "closer": ema_closer, "etf": TimeFrame.M15, "ecc": 5000,
                  "entry_ema": 5, "stf": TimeFrame.H1}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'NFF'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or PTrader(symbol=self.symbol)
        self.tracker: Tracker = Tracker(snooze=self.interval.time)

    async def check_trend(self):
        try:
            fcandles = await self.symbol.copy_rates_from_pos(timeframe=self.ftf, count=self.fcc)
            if not ((current := fcandles[-1].time) >= self.tracker.ftf_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, ftf_time=current, order_type=None)
            fcandles.ta.ema(length=self.first_ema, append=True)
            fcandles.ta.ema(length=self.second_ema, append=True)
            fcandles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second"})

            fcandles['cas'] = fcandles.ta_lib.above(fcandles.close, fcandles.second)
            fcandles['saf'] = fcandles.ta_lib.above(fcandles.second, fcandles.first)

            fcandles['cbs'] = fcandles.ta_lib.below(fcandles.close, fcandles.second)
            fcandles['sbf'] = fcandles.ta_lib.below(fcandles.second, fcandles.first)
            current = fcandles[-1]

            if current.is_bullish() and all([current.cas, current.saf]):
                scandles = await self.symbol.copy_rates_from_pos(timeframe=self.stf, count=self.scc)
                if not ((current := scandles[-1].time) >= self.tracker.stf_time):
                    self.tracker.update(new=False, order_type=None)
                    return
                self.tracker.update(new=True, stf_time=current, order_type=None)
                scandles.ta.ema(length=self.third_ema, append=True)
                scandles.ta.ema(length=self.fourth_ema, append=True)
                scandles.rename(inplace=True, **{f"EMA_{self.third_ema}": "third", f"EMA_{self.fourth_ema}": "fourth"})
                scandles['caf'] = scandles.ta_lib.above(scandles.close, scandles.fourth)
                scandles['fat'] = scandles.ta_lib.above(scandles.fourth, scandles.third)
                current = scandles[-1]

                if current.is_bullish() and all([current.caf, current.fat]):
                    ecandles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
                    if not ((current := ecandles[-1].time) >= self.tracker.etf_time):
                        self.tracker.update(new=False, order_type=None)
                        return
                    self.tracker.update(new=True, etf_time=current, order_type=None)
                    ecandles.ta.ema(length=self.entry_ema, append=True)
                    ecandles.rename(inplace=True, **{f"EMA_{self.entry_ema}": "entry"})
                    ecandles['cae'] = ecandles.ta_lib.cross(ecandles.close, ecandles.entry, above=True)
                    current = ecandles[-1]
                    if current.is_bullish() and current.cae:
                        self.tracker.update(trend="bullish", snooze=self.stf.time, order_type=OrderType.BUY)
                    else:
                        self.tracker.update(snooze=self.etf.time, order_type=None)
                else:
                    self.tracker.update(snooze=self.stf.time, order_type=None)

            elif current.is_bearish() and all([current.cbs, current.sbf]):
                scandles = await self.symbol.copy_rates_from_pos(timeframe=self.stf, count=self.scc)
                if not ((current := scandles[-1].time) >= self.tracker.stf_time):
                    self.tracker.update(new=False, order_type=None)
                    return
                self.tracker.update(new=True, stf_time=current, order_type=None)
                scandles.ta.ema(length=self.third_ema, append=True)
                scandles.ta.ema(length=self.fourth_ema, append=True)
                scandles.rename(inplace=True, **{f"EMA_{self.third_ema}": "third", f"EMA_{self.fourth_ema}": "fourth"})
                scandles['cbf'] = scandles.ta_lib.below(scandles.close, scandles.fourth)
                scandles['fbt'] = scandles.ta_lib.below(scandles.fourth, scandles.third)
                current = scandles[-1]
                if current.is_bearish() and all([current.cbf, current.fbt]):
                    ecandles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
                    if not ((current := ecandles[-1].time) >= self.tracker.etf_time):
                        self.tracker.update(new=False, order_type=None)
                        return
                    self.tracker.update(new=True, etf_time=current, order_type=None)
                    ecandles.ta.ema(length=self.entry_ema, append=True)
                    ecandles.rename(inplace=True, **{f"EMA_{self.entry_ema}": "entry"})
                    ecandles['cbe'] = ecandles.ta_lib.cross(ecandles.close, ecandles.entry, above=False)
                    current = ecandles[-1]
                    if current.is_bearish() and current.cbe:
                        self.tracker.update(trend="bearish", snooze=self.stf.time, order_type=OrderType.SELL)
                    else:
                        self.tracker.update(snooze=self.etf.time, order_type=None)
                        return
                else:
                    self.tracker.update(snooze=self.stf.time, order_type=None)

            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def watch_market(self):
        await self.check_trend()

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
