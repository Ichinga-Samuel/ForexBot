from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.ema_closer import ema_closer
from ..traders.s_trader import STrader
from ..utils.ram import RAM

logger = getLogger(__name__)


class RMomentum(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    sma_length: int
    rsi_length: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.H1
    ecc: int
    parameters = {"first_ema": 5, "second_ema": 8, "third_ema": 13, "ttf": TimeFrame.H4, "tcc": 720,
                  'closer': ema_closer, "etf": TimeFrame.M15, 'ecc': 2880, 'sma_length': 9, 'rsi_length': 9}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'RMomentum'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or STrader(symbol=self.symbol)
        self.tracker: Tracker = Tracker(snooze=self.ttf.time, sl=0)

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
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first",
                                            f"EMA_{self.second_ema}": "second", f"EMA_{self.third_ema}": "third"})

            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['sat'] = candles.ta_lib.above(candles.second, candles.third)
            candles['sbt'] = candles.ta_lib.below(candles.second, candles.third)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles.ta.adx(append=True)
            candles.rename(**{'ADX_14': 'adx'})
            candles.ta.sma(close='adx', length=self.sma_length, append=True)
            candles.rename(**{f'SMA_{self.sma_length}': 'sma'})
            candles.ta.rsi(close='sma', length=self.rsi_length, append=True)
            candles.rename(**{f'RSI_{self.rsi_length}': 'rsi'})
            candles['abs'] = candles.ta_lib.above(candles.adx, candles.sma)
            current = candles[-1]
            if current.rsi <= 70 and current.abs:
                if all([current.fas, current.sat]):
                    self.tracker.update(trend='bullish')

                elif all([current.fbs, current.sat]):
                    self.tracker.update(trend='bearish')
                else:
                    self.tracker.update(trend="ranging", snooze=self.interval.time)
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.macd(append=True)
            candles.rename(**{'MACD_12_26_9': 'macd', 'MACDh_12_26_9': 'macdh', 'MACDs_12_26_9': 'macds'})
            candles['mxs'] = candles.ta_lib.cross(candles.macd, candles.macds)
            candles['mxsb'] = candles.ta_lib.cross(candles.macd, candles.macds, above=False)
            candles['hxz'] = candles.ta_lib.cross_value(candles.macdh, 0)
            candles['hxbz'] = candles.ta_lib.cross_value(candles.macdh, 0, above=False)
            current = candles[-1]
            if self.tracker.bullish and (current.mxs or current.hxz):
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY)
            elif self.tracker.bearish and (current.mxsb or current.hxbz):
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(snooze=self.etf.time, order_type=None)
        except Exception as exe:
            self.tracker.update(snooze=self.etf.time, order_type=None)
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.confirm_trend")

    async def watch_market(self):
        await self.check_trend()
        if not self.tracker.ranging:
            await self.confirm_trend()

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.interval.time)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters,
                                                  sl=self.tracker.sl)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
