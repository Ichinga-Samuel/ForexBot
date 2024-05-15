from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.adx_closer import adx_closer
from ..traders.point_trader import PointTrader

logger = getLogger(__name__)


class ADXScalper2(Strategy):
    etf: TimeFrame
    parameters: dict
    adx: int
    trader: Trader
    tracker: Tracker
    adx_cutoff: int
    interval: TimeFrame = TimeFrame.M2
    timeout: TimeFrame = TimeFrame.M15
    points: int
    parameters = {"closer": adx_closer, "etf": TimeFrame.M5, "adx": 3, "exit_timeframe": TimeFrame.M5, "ecc": 864,
                  "points": 50, "adx_cutoff": 30}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'ADXScalper2'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or PointTrader(symbol=self.symbol, track_trades=True)
        self.tracker: Tracker = Tracker(snooze=self.etf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, entry_time=current, order_type=None)

            candles.ta.adx(length=self.adx, append=True)
            candles.rename(inplace=True, **{f"ADX_{self.adx}": "adx", f"DMP_{self.adx}": "dmp",
                                            f"DMN_{self.adx}": "dmn"})
            candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn)
            candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp)
            current = candles[-1]
            prev = candles[-2]
            prev2 = candles[-3]

            flat_bottom = prev.is_bullish() and prev2.is_bearish()
            flat_top = prev.is_bearish() and prev2.is_bullish()
            bottom_diff = abs(prev2.close - prev.open) / min(prev2.close, prev.open) <= 0.02
            top_diff = abs(prev2.close - prev.open) / min(prev.high, prev2.high) <= 0.02
            flat_bottom = flat_bottom and bottom_diff
            flat_top = flat_top and top_diff

            if current.adx >= self.adx_cutoff and current.pxn and current.is_bullish() and flat_bottom:
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.BUY)

            elif current.adx >= self.adx_cutoff and current.nxp and current.is_bearish() and flat_top:
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.tracker.snooze)
            while True:
                await sess.check()
                try:
                    await self.check_trend()
                    if not self.tracker.new:
                        await asyncio.sleep(2)
                        continue
                    if self.tracker.order_type is None:
                        await self.sleep(self.tracker.snooze)
                        continue
                    await self.trader.place_trade(order_type=self.tracker.order_type, points=self.points,
                                                  parameters=self.parameters)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
