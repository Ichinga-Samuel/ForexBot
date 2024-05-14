import asyncio
import logging

from aiomql import Tracker, ForexSymbol, TimeFrame, OrderType, Sessions, Strategy, Candles, Trader

from ..traders.b_trader import BTrader
from ..closers.ema_closer import ema_closer
logger = logging.getLogger(__name__)


class FingerTrap(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    fast_ema: int
    slow_ema: int
    entry_ema: int
    ecc: int
    tcc: int
    trend_interval: TimeFrame = TimeFrame.M5
    entry_interval: TimeFrame = TimeFrame.M2
    trader: Trader
    tracker: Tracker

    parameters = {"fast_ema": 8, "slow_ema": 21, "etf": TimeFrame.M5, 'closer': ema_closer,
                  "ttf": TimeFrame.H1, "entry_ema": 5, "tcc": 720, "ecc": 4032}  

    def __init__(self, *, symbol: ForexSymbol, params: dict | None = None, trader: Trader = None,
                 sessions: Sessions = None, name: str = 'FingerTrap'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or BTrader(symbol=self.symbol)
        self.tracker: Tracker = Tracker(snooze=self.trend_interval.time)  

    async def check_trend(self):
        try:
            candles: Candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc) 
            if not ((current := candles[-1].time) >= self.tracker.trend_time):  
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current, order_type=None)
            candles.ta.ema(length=self.slow_ema, append=True, fillna=0)
            candles.ta.ema(length=self.fast_ema, append=True, fillna=0)
            candles.ta.adx(append=True)
            candles.rename(inplace=True, **{f"EMA_{self.fast_ema}": "fast", f"EMA_{self.slow_ema}": "slow",
                                            "ADX_14": "adx", "DMP_14": "dmp", "DMN_14": "dmn"})  

            candles['caf'] = candles.ta_lib.above(candles.close, candles.fast)
            candles['fas'] = candles.ta_lib.above(candles.fast, candles.slow)

            candles['fbs'] = candles.ta_lib.below(candles.fast, candles.slow)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.fast)  
            current = candles[-1]
            if current.is_bullish() and current.fas and current.caf and current.adx > 25 and current.dmp > current.dmn:
                self.tracker.update(trend="bullish")
            elif current.is_bearish() and current.fbs and current.cbf and current.dmn > current.dmp:
                self.tracker.update(trend="bearish") 
            else:
                self.tracker.update(trend="ranging", snooze=self.trend_interval.time, order_type=None)  
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.trend_interval.time, order_type=None)

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)  
                return
            self.tracker.update(new=True, entry_time=current, order_type=None)
            candles.ta.ema(length=self.entry_ema, append=True)
            candles.ta.adx(length=3)
            candles.rename(**{f"EMA_{self.entry_ema}": "ema", "ADX_3": "adx", "DMP_3": "dmp", "DMN_3": "dmn"})
            candles['cae'] = candles.ta_lib.above(candles.close, candles.ema)
            candles['cbe'] = candles.ta_lib.below(candles.close, candles.ema)
            candels['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn)
            candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp)
            current = candles[-1]

            if self.tracker.bullish and current.cae and current.pxn and current.is_bullish() and current.adx > 25:
                self.tracker.update(snooze=self.trend_interval.time, order_type=OrderType.BUY)
            elif self.tracker.bearish and current.cbe and current.nxp and current.is_bearish() and current.adx > 25:
                self.tracker.update(snooze=self.trend_interval.time, order_type=OrderType.SELL) 
            else:
                self.tracker.update(snooze=self.entry_interval.time, order_type=None)
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.confirm_trend")
            self.tracker.update(snooze=self.entry_interval.time, order_type=None)

    async def watch_market(self):
        await self.check_trend()
        if not self.tracker.ranging:
            await self.confirm_trend()  # 12

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.trend_interval.time)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters)  # 13
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} For {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.interval.time)
