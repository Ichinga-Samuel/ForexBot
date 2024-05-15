from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.ram import RAM
from ..closers.adx_closer import adx_closer
from ..traders.sp_trader import SPTrader

logger = getLogger(__name__)


class ADXScalper(Strategy):
    etf: TimeFrame
    parameters: dict
    atr_multiplier: int
    atr_factor: int
    adx_cutoff: int
    atr_length: int
    adx: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M2
    timeout: TimeFrame = TimeFrame.M15
    parameters = {"closer": adx_closer, "etf": TimeFrame.M5, "adx": 3, "exit_timeframe": TimeFrame.M5, "ecc": 864,
                  "atr_multiplier": 1.5, "adx_cutoff": 30, "atr_factor": 1.5, "atr_length": 14}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'ADXScalper'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        ram = RAM(risk_to_reward=1/3, min_amount=3.6, max_amount=3.6)
        self.trader = trader or SPTrader(symbol=self.symbol, track_trades=True, ram=ram)
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
            bottom_diff = abs(prev2.close - prev.open) / min(prev2.close, prev.open) <= 0.02
            top_diff = abs(prev2.close - prev.open) / min(prev.high, prev2.high) <= 0.02
            flat_bottom = flat_bottom and bottom_diff
            flat_top = flat_top and top_diff

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
