from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.top_bottom import double_top, double_bottom
from ..closers.adx_closer import adx_closer
from ..traders.sp_trader import SPTrader

logger = getLogger(__name__)


class ADXCrossing(Strategy):
    etf: TimeFrame
    parameters: dict
    atr_multiplier: float
    atr_factor: float
    adx_cutoff: int
    atr_length: int
    adx: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M5
    timeout: TimeFrame = TimeFrame.H2
    parameters = {"exit_function": adx_closer, "etf": TimeFrame.M30, "adx": 14, "exit_timeframe": TimeFrame.M30,
                  "ecc": 864, "atr_multiplier": 1, "adx_cutoff": 23, "atr_factor": 0.25, "atr_length": 14,
                  "excc": 864, "tptf": TimeFrame.M30, "tpcc": 720, "exit_adx": 7}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'ADXCrossing'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or SPTrader(symbol=self.symbol, track_loss=False, hedge_order=False,
                                         track_profit_params={"trail_start": 0.3})
        self.tracker: Tracker = Tracker(snooze=self.etf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if (current := candles[-1].time) < self.tracker.entry_time:
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, entry_time=current, order_type=None)
            candles.ta.adx(length=self.adx, append=True, mamode='ema')
            candles.ta.atr(append=True, length=self.atr_length)
            candles.rename(inplace=True, **{f"ADX_{self.adx}": "adx", f"DMP_{self.adx}": "dmp",
                                            f"DMN_{self.adx}": "dmn", f"ATRr_{self.atr_length}": "atr"})
            candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn, asint=False)
            candles['nxp'] = candles.ta_lib.cross(candles.dmn, candles.dmp, asint=False)
            current = candles[-1]
            if current.adx > self.adx_cutoff and current.pxn:
                self.tracker.update(trend="bullish")
            elif current.adx > self.adx_cutoff and current.nxp:
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
                return
            second = candles[-2]
            first = candles[-3]

            if self.tracker.bullish and double_bottom(first=first, second=second) and current.is_bullish():
                sl = min(second.low, first.low)
                tp = current.close + (current.close - sl) * self.trader.ram.risk_to_reward
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.BUY, sl=sl, tp=tp)

            elif self.tracker.bearish and double_top(first=first, second=second) and current.is_bearish():
                sl = max(second.high, first.high)
                tp = current.close + (sl - current.close) * self.trader.ram.risk_to_reward
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.SELL, sl=sl, tp=tp)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, sl=self.tracker.sl,
                                                  tp=self.tracker.tp, parameters=self.parameters)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
