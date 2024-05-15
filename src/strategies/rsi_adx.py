from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.adx_closer import adx_closer
from ..traders.point_trader import PointTrader

logger = getLogger(__name__)


class RA(Strategy):
    ttf: TimeFrame
    ema: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M1
    timeout: TimeFrame = TimeFrame.H1
    parameters = {"ema": 50, "ttf": TimeFrame.M5, "tcc": 4320}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'RA'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or PointTrader(symbol=self.symbol, track_trades=False)
        self.tracker: Tracker = Tracker(snooze=self.timeout.time)

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
            candles.rename(inplace=True, **{f"EMA_{self.ema}": "ema", "ADX_5": "adx", f"RSI_3": "rsi"})
            candles['cae'] = candles.ta_lib.above(candles.close, candles.ema)
            candles['cbe'] = candles.ta_lib.below(candles.close, candles.ema)
            trend = candles[-1: -13]

            current = candles[-1]
            prev = candles[-2]

            if all(trend.cae) and current.rsi <= 20 and current.adx >= 30:
                self.tracker.update(trend='bullish', order_type=None)

            elif all(trend.cbe) and current.adx >= 30 and current.rsi >= 80:
                self.tracker.update(trend='bearish', order_type=None)

            else:
                self.tracker.update(snooze=self.ttf.time, order_type=None)
                return

            if self.tracker.bullish and current.high > prev.high and current.is_bullish():
                self.tracker.update(order_type=OrderType.BUY, snooze=self.timeout.time)

            elif self.tracker.bearish and current.low < prev.low and current.is_bearish():
                self.tracker.update(order_type=OrderType.SELL, snooze=self.timeout.time)
            else:
                self.tracker.update(snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

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
                    await self.confirm_trend()
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
