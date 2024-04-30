from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.stoch_closer import stoch_closer
from ..traders.p_trader import PTrader

logger = getLogger(__name__)


class FingerADX(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    price_sma: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.H1
    timeout: int = 7200
    parameters = {"first_ema": 2, "second_ema": 5, "third_ema": 8, "ttf": TimeFrame.H4, "tcc": 720,
                  'closer': stoch_closer, "price_sma": 50}

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
            candles.ta.ema(length=self.third_ema, append=True)
            candles.ta.sma(close='close', length=self.price_sma, append=True)
            candles.ta.adx(append=True, lensig=50)

            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"EMA_{self.third_ema}": "third", f"ADX_50": "adx",
                                            f"SMA_{self.price_sma}": "sma"})
            candles.ta.sma(close='adx', length=13, append=True)
            candles.rename(inplace=True, **{'SMA_13': 'adx_sma'})
            candles.ta.stoch(append=True)
            candles.rename(inplace=True, **{'STOCHd_14_3_3': 'stoch'})
            candles.ta.sma(close='stoch', length=5, append=True)
            candles.rename(inplace=True, **{'SMA_5': 'stoch_sma'})

            candles['sas'] = candles.ta_lib.above(candles.stoch, candles.stoch_sma)
            candles['cas'] = candles.ta_lib.above(candles.close, candles.sma)
            candles['caf'] = candles.ta_lib.above(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['sat'] = candles.ta_lib.above(candles.second, candles.third)
            candles['aas'] = candles.ta_lib.above(candles.adx, candles.adx_sma)

            candles['sbs'] = candles.ta_lib.below(candles.stoch, candles.stoch_sma)
            candles['cbs'] = candles.ta_lib.below(candles.close, candles.sma)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles['sbt'] = candles.ta_lib.below(candles.second, candles.third)

            current = candles[-1]
            if current.is_bullish() and all([current.cas, current.caf, current.fas, current.sat, current.aas,
                                             current.sas]):
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY)

            elif current.is_bearish() and all([current.cbs, current.cbf, current.fbs, current.sbt, current.aas,
                                               current.sbs]):
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters)
                    await asyncio.sleep(self.timeout)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
