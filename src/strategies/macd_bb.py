import asyncio
import logging

from aiomql import Symbol, Trader, Candles, Strategy, TimeFrame, OrderType, Sessions, Tracker, SimpleTrader

logger = logging.getLogger(__name__)


class MACDonBB(Strategy):
    trend_time_frame: TimeFrame
    entry_time_frame: TimeFrame
    trend: int
    fast_period: int
    slow_period: int
    parameters: dict
    prices: Candles
    interval: float
    entry_candles_count: int
    trend_candles_count: int
    trader: Trader
    _parameters = {"trend": 3, "fast_period": 8, "slow_period": 34, "entry_time_frame": TimeFrame.M5,
                   "trend_time_frame": TimeFrame.H1,
                   "trend_candles_count": 48, "entry_candles_count": 100}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'MACDonBB'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or SimpleTrader(symbol=self.symbol)
        self.tracker: Tracker = Tracker(snooze=self.trend_time_frame.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.trend_time_frame,
                                                            count=self.trend_candles_count)
            current = candles[-1]
            if current.time >= self.tracker.trend_time:
                self.tracker.update(new=True, trend_time=current.time)
            else:
                self.tracker.update(new=False)
                return

            candles.ta.sma(length=self.slow_period, append=True, fillna=0)
            candles.ta.sma(length=self.fast_period, append=True, fillna=0)
            candles.rename(inplace=True, **{f"SMA_{self.fast_period}": "fast", f"SMA_{self.slow_period}": "slow"})

            # Compute
            candles["fast_A_slow"] = candles.ta_lib.above(candles.fast, candles.slow)
            candles["fast_B_slow"] = candles.ta_lib.below(candles.fast, candles.slow)
            candles["close_A_fast"] = candles.ta_lib.above(candles.close, candles.fast)
            candles["close_B_fast"] = candles.ta_lib.below(candles.close, candles.fast)

            trend = candles[-self.trend: -1]
            if all(c.fast_A_slow and c.close_A_fast for c in trend):
                self.tracker.update(trend="bullish")

            elif all(c.fast_B_slow and c.close_B_fast for c in trend):
                self.tracker.update(trend="bearish")

            else:
                self.tracker.update(trend="ranging", snooze=self.trend_time_frame.time)
        except Exception as exe:
            logger.error(f"{exe}. Error in {self.__class__.__name__}.check_trend")

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.entry_time_frame,
                                                            count=self.entry_candles_count)
            current = candles[-1]
            if current.time > self.tracker.entry_time:
                self.tracker.update(new=True, entry_time=current.time)
            else:
                self.tracker.update(new=False)
                return
            candles.ta.bbands(append=True, fillna=0)
            candles.ta.macd(append=True, fillna=0)
            candles.rename(inplace=True, **{f"MACD_12_26_9": "macd", f"BBL_5_2.0": "bblower", f"BBM_5_2.0": "bbmid",
                                            f"BBU_5_2.0": "bbupper", f"MACDh_12_26_9": "macdh",
                                            f"MACDs_12_26_9": "macds"})
            candles["macd_XA_bbupper"] = candles.ta_lib.cross(candles.macd, candles.bbupper)
            candles["macd_XB_bblower"] = candles.ta_lib.cross(candles.macd, candles.bblower, above=False)
            current = candles[-2]
            if self.tracker.bullish and current.macd_XA_bbupper:
                self.tracker.update(snooze=self.trend_time_frame.time, order=OrderType.BUY)
            elif self.tracker.bearish and current.macd_XB_bblower:
                self.tracker.update(snooze=self.trend_time_frame.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(snooze=self.entry_time_frame.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} Error in {self.__class__.__name__}.confirm_trend")

    async def watch_market(self):
        await self.check_trend()
        if not self.tracker.ranging:
            await self.confirm_trend()

    async def trade(self):
        logger.info(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
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
                    self.tracker.order_type = None
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.trend_time_frame.time)
                    continue