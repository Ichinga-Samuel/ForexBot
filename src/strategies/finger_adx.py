from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..traders.p_trader import PTrader

logger = getLogger(__name__)


class FingerADX(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    price_sma: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M15
    timeout: int = TimeFrame.H2
    parameters = {"first_ema": 2, "second_ema": 3, "ttf": TimeFrame.H1, "tcc": 720, "price_sma": 50}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'FingerADX'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or PTrader(symbol=self.symbol)
        self.tracker: Tracker = Tracker(snooze=self.interval.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current, order_type=None)
            candles.ta.ema(length=self.first_ema, append=True)
            candles.ta.ema(length=self.second_ema, append=True)
            candles.ta.sma(close='close', length=self.price_sma, append=True)
            candles.ta.adx(append=True)
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"ADX_14": "adx", f"SMA_{self.price_sma}": "sma"})

            candles['cas'] = candles.ta_lib.above(candles.close, candles.sma)
            candles['caf'] = candles.ta_lib.above(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)

            candles['cbs'] = candles.ta_lib.below(candles.close, candles.sma)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)

            current = candles[-1]
            prev = candles[-2]
            higher_high = current.high > prev.high
            lower_low = current.low < prev.low

            if (current.is_bullish() and current.adx >= 25 and all([current.cas, current.caf, current.fas])
                and higher_high):
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY)

            elif (current.is_bearish() and current.adx >= 25 and all([current.cbs, current.cbf, current.fbs])
                  and lower_low):
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            # await self.sleep(self.tracker.snooze)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters)
                    # await asyncio.sleep(self.timeout)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
