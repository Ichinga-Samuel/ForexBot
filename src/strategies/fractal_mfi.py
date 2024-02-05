from logging import getLogger
import asyncio
import warnings

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..traders.sp_trader import SPTrader
from ..utils.patterns import find_bearish_fractal, find_bullish_fractal

logger = getLogger(__name__)


class FractalMFI(Strategy):
    tracker: Tracker
    ema: int
    lower_mfi: int
    upper_mfi: int
    ttf: TimeFrame
    tcc: int
    parameters = {'ema': 13, 'lower_mfi': 30, 'upper_mfi': 70, 'ttf': TimeFrame.H1, 'tcc': 168}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None, name: str = 'FractalMFI',
                 trader: Trader = None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or SPTrader(symbol=self.symbol)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return

            self.tracker.update(new=True, trend_time=current)
            warnings.filterwarnings("ignore")
            candles.ta.mfi(volume='tick_volume', append=True)
            candles.rename(**{'MFI_14': 'mfi'})
            candles.ta.ema(close='mfi', length=self.ema, append=True)
            candles.rename(**{f'EMA_{self.ema}': 'ema'})
            above = candles.ta_lib.cross(candles.mfi, candles.ema)
            below = candles.ta_lib.cross(candles.mfi, candles.ema, above=False)
            mfi = candles[-1].mfi
            trend = candles[-2:]
            if mfi <= self.lower_mfi and above.iloc[-1]:
                sl = getattr(find_bullish_fractal(trend), 'low', None) or trend.low.min()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl)
            elif mfi >= self.upper_mfi and below.iloc[-1]:
                sl = getattr(find_bearish_fractal(trend), 'high', None) or trend.high.max()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL, sl=sl)
            else:
                self.tracker.update(trend="ranging", order_type=None, snooze=self.ttf.time)
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.check_trend\n")
            self.tracker.update(snooze=self.ttf.time, order_type=None)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.ttf.time)
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
                    logger.error(f"{err} For {self.symbol} in {self.__class__.__name__}.trade\n")
                    await self.sleep(self.ttf.time)