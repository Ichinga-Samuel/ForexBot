from logging import getLogger
import asyncio

from aiomql import Symbol, Candles, Strategy, TimeFrame, Sessions, OrderType, Trader
from ..utils.tracker import Tracker
from ..utils.patterns import find_bearish_fractal, find_bullish_fractal
from ..traders.sl_trader import SLTrader

logger = getLogger(__name__)


class FractalADIMACD(Strategy):
    tracker: Tracker
    ecc: int
    tcc: int
    ttf: TimeFrame
    etf: TimeFrame
    rsi_upper: int
    rsi_lower: int
    parameters = {"ecc": 84, "tcc": 42, "ttf": TimeFrame.H4, "etf": TimeFrame.M30, 'rsi_upper': 65, 'rsi_lower': 35}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None,
                 name: str = 'FractalADIMACD', trader: Trader = None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or SLTrader(symbol=self.symbol)

    async def check_trend(self):
        try:
            candles: Candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.new = False
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.ad(volume="tick_volume", append=True)
            candles.ta.rsi(close="AD", append=True)
            candles.rename(**{f'RSI_{14}': 'rsi'})
            rsi = candles[-1].rsi
            if 0 < rsi <= self.rsi_lower:
                self.tracker.update(trend="bullish")
            elif self.rsi_upper <= rsi <= 100:
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging")
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.check_trend\n")
            self.tracker.update(snooze=self.ttf.time, order_type=None)

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, entry_time=current)
            candles.ta.macd(append=True, fillna=0)
            candles.rename(inplace=True, **{f"MACD_12_26_9": "macd", f"MACDh_12_26_9": "macdh",
                                            f"MACDs_12_26_9": "macds"})
            above = candles.ta_lib.cross(candles["macd"], candles["macds"])
            below = candles.ta_lib.cross(candles["macd"], candles["macds"], above=False)
            trend = candles[-25: -1]
            if self.tracker.bullish and above.iloc[-1]:
                sl = getattr(find_bullish_fractal(trend), 'low', None) or trend.low.min()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl)
            elif self.tracker.bearish and below.iloc[-1]:
                sl = getattr(find_bearish_fractal(trend), 'high', None) or trend.high.max()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL, sl=sl)
            else:
                self.tracker.update(snooze=self.etf.time, order_type=None)
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.confirm_trend\n")
            self.tracker.update(snooze=self.etf.time, order_type=None)

    async def watch_market(self):
        await self.check_trend()
        if not self.tracker.ranging:
            await self.confirm_trend()

    async def trade(self):
        logger.info(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.etf.time)
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