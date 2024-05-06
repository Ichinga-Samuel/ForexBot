from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.adx_closer import adx_closer
from ..traders.b_trader import BTrader

logger = getLogger(__name__)


class RA(Strategy):
    ttf: TimeFrame
    htf: TimeFrame
    ema: int
    parameters: dict
    tcc: int
    hcc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M1
    timeout: TimeFrame = TimeFrame.H1
    parameters = {"ema": 50, "ttf": TimeFrame.M5, "tcc": 4320, "htf": TimeFrame.H1, "hcc": 360}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'RA'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or BTrader(symbol=self.symbol, track_trades=False)
        self.tracker: Tracker = Tracker(snooze=self.htf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.htf, count=self.hcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current, order_type=None)
            candles.ta.ema(length=self.ema, append=True)
            candles.ta.adx(append=True)
            candles.ta.rsi(append=True)
            candles.rename(inplace=True, **{f"EMA_{self.ema}": "ema",
                                            "ADX_14": "adx", "DMP_14": "dmp", "DMN_14": "dmn", f"RSI_14": "rsi"})

            candles['cas'] = candles.ta_lib.above(candles.close, candles.first)
            candles['cbs'] = candles.ta_lib.below(candles.close, candles.first)
            current = candles[-1]
            prev = candles[-2]

            if prev.dmp < current.dmp > current.dmn and current.rsi < 30 and current.cas and current.adx >= 25:
                self.tracker.update(trend='bullish')

            elif prev.dmn < current.dmn > current.dmp and current.adx >= 25 and current.rsi > 70 and current.cbs:
                self.tracker.update(trend='bearish')
            else:
                self.tracker.update(trend="ranging", snooze=self.htf.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.ttf.time, order_type=None)

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current, order_type=None)
            candles.ta.ema(length=self.ema, append=True)
            candles.ta.adx(append=True, length=5)
            candles.ta.rsi(append=True, length=3)
            candles.rename(inplace=True, **{f"EMA_{self.ema}": "ema",
                                            "ADX_5": "adx", "DMP_5": "dmp", "DMN_5": "dmn", f"RSI_3": "rsi"})

            candles['cas'] = candles.ta_lib.above(candles.close, candles.first)
            candles['cbs'] = candles.ta_lib.below(candles.close, candles.first)
            current = candles[-1]
            prev = candles[-2]

            if self.tracker.bullish and current.cas and current.dmp > current.dmn and current.rsi < 20 and current.adx > 30 and current.high > prev.high:
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.BUY)

            elif self.tracker.bearish and prev.dmn < current.dmn > current.dmp and current.adx > 30 and current.rsi > 80 and current.cbs and current.low < prev.low:
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def watch_market(self):
        await self.check_trend()
        if not self.ranging:
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
                    # await asyncio.sleep(self.timeout)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
