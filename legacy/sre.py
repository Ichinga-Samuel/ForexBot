from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader
from aiomql.utils import find_bearish_fractal, find_bullish_fractal
from ..closers.ema_rsi_closer import ema_rsi_closer
from ..utils.tracker import Tracker
from ..traders.sp_trader import SPTrader

logger = getLogger(__name__)


class SRE(Strategy):
    etf: TimeFrame
    first_ema: int
    second_ema: int
    rsi_level: int
    stoch_overbought: int
    stoch_oversold: int
    rsi_overbought: int
    rsi_oversold: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    trend: int
    parameters = {"first_ema": 5, "second_ema": 10, "etf": TimeFrame.M15, "tcc": 168, 'trend': 24, 'rsi_level': 50,
                  'stoch_overbought': 75, 'rsi_overbought': 75, 'rsi_oversold': 25, 'stoch_oversold': 25,
                  'closer': ema_rsi_closer}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'SRE'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or SPTrader(symbol=self.symbol, track_trades=True)
        self.tracker: Tracker = Tracker(snooze=self.etf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.ema(length=self.first_ema, append=True)
            candles.ta.ema(length=self.second_ema, append=True)
            candles.ta.rsi(append=True)
            candles.ta.stoch(append=True)
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"RSI_14": "rsi", "STOCHk_14_3_3": "stochk", "STOCHd_14_3_3": "stochd"})

            candles['caf'] = candles.ta_lib.cross(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.cross(candles.first, candles.second)

            candles['cbf'] = candles.ta_lib.cross(candles.close, candles.first, above=False)
            candles['fbs'] = candles.ta_lib.cross(candles.first, candles.second, above=False)
            current = candles[-1]
            if (all([current.caf, current.fas]) and (self.rsi_level < current.rsi < self.rsi_overbought) and
                    max(current.stochk, current.stochd) < self.stoch_overbought):
                sl = find_bullish_fractal(candles).low
                self.tracker.update(sl=sl, snooze=self.etf.time, order_type=OrderType.BUY)

            elif (all([current.cbf, current.fbs]) and (self.rsi_level > current.rsi > self.rsi_oversold) and
                  min(current.stochk, current.stochd) > self.stoch_oversold):
                sl = find_bearish_fractal(candles).high
                self.tracker.update(snooze=self.etf.time, order_type=OrderType.SELL, sl=sl)
            else:
                self.tracker.update(trend="ranging", snooze=self.etf.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend\n")
            self.tracker.update(snooze=self.etf.time, order_type=None)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.etf.time)
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
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade\n")
                    await self.sleep(self.etf.time)
