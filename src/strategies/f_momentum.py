from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader
# from aiomql.utils import find_bearish_fractal, find_bullish_fractal

from ..utils.tracker import Tracker
from ..closers.ema_closer import ema_closer
from ..traders.p_trader import PTrader
from ..utils.ram import RAM

logger = getLogger(__name__)


class FMomentum(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    sma_length: int
    rsi_length: int
    tcc: int
    parameters: dict
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M30
    parameters = {"first_ema": 5, "second_ema": 8, "third_ema": 13, "ttf": TimeFrame.H4, "tcc": 720, 'trend': 2,
                  'closer': ema_closer, "etf": TimeFrame.M30, 'ecc': 2880, 'sma_length': 9, 'rsi_length': 9}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'FMomentum'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or PTrader(symbol=self.symbol, ram=RAM(risk_to_reward=3),
                                        trail_profits={'trail_start': 0.375})
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
            candles['abs'] = candles.ta_lib.cross(candles.adx, candles.sma)
            current = candles[-1]
            if current.rsi <= 70 and current.abs:
                if all([current.fas, current.sat]):
                    self.tracker.update(trend='bullish', snooze=self.ttf.time, order_type=OrderType.BUY)

                elif all([current.fbs, current.sat]):
                    self.tracker.update(trend='bearish', snooze=self.ttf.time, order_type=OrderType.SELL)
                else:
                    self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

    async def watch_market(self):
        await self.check_trend()

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
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade\n")
                    await self.sleep(self.tracker.snooze)
