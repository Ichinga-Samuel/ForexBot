from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.ram import RAM
from ..closers.adx_closer import adx_closer
from ..traders.sp_trader import SPTrader

logger = getLogger(__name__)


class ADXCrossing(Strategy):
    etf: TimeFrame
    parameters: dict
    atr_multiplier: int
    atr_factor: int
    adx_cutoff: int
    atr_length: int
    adx: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M5
    timeout: TimeFrame = TimeFrame.H1
    parameters = {"closer": adx_closer, "etf": TimeFrame.M30, "adx": 3, "exit_timeframe": TimeFrame.M30, "ecc": 864,
                  "atr_multiplier": 2.5, "adx_cutoff": 25, "atr_factor": 1.5, "atr_length": 14}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'ADXCrossing'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        ram = RAM(min_amount=6, max_amount=6, risk_to_reward=1/3)
        self.trader = trader or SPTrader(symbol=self.symbol, track_trades=True)
        self.tracker: Tracker = Tracker(snooze=self.etf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, entry_time=current, order_type=None)

            candles.ta.adx(length=self.adx, append=True)
            candles.ta.atr(append=True, length=self.atr_length)
            candles.rename(inplace=True, **{f"ADX_{self.adx}": "adx", f"DMP_{self.adx}": "dmp",
                                            f"DMN_{self.adx}": "dmn", f"ATRr_{self.atr_length}": "atr"})
            candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn)
            candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp)
            current = candles[-1]
            prev = candles[-2]
            prev2 = candles[-3]
            flat_bottom = prev.is_bullish() and prev2.is_bearish()
            flat_top = prev.is_bearish() and prev2.is_bullish()
            low_diff = abs(prev.low - prev2.low) / min(prev.low, prev2.low) <= 0.02
            high_diff = abs(prev.high - prev2.high) / min(prev.high, prev2.high) <= 0.02
            flat_bottom = flat_bottom and low_diff
            flat_top = flat_top and high_diff

            if current.adx >= self.adx_cutoff and current.pxn and current.is_bullish() and flat_bottom:
                sl = current.low - (current.atr * self.atr_multiplier)
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.BUY, sl=sl)

            elif current.adx >= self.adx_cutoff and current.nxp and current.is_bearish() and flat_top:
                sl = current.high + (current.atr * self.atr_multiplier)
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.SELL, sl=sl)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters,
                                                  sl=self.tracker.sl)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
