from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.patterns import find_bearish_fractal, find_bullish_fractal
from ..traders.sl_trader import SLTrader

logger = getLogger(__name__)


class FingerFractal(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    trend: int
    fast_ema: int
    slow_ema: int
    entry_ema: int
    parameters: dict
    ecc: int
    tcc: int
    trader: Trader
    tracker: Tracker
    parameters = {"trend": 3, "fast_ema": 8, "slow_ema": 20, "etf": TimeFrame.M5,
                  "ttf": TimeFrame.H1, "entry_ema": 5, "tcc": 50, "ecc": 600, 'used_fractal': True}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'FingerFractal'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or SLTrader(symbol=self.symbol, multiple=False, use_telegram=False)
        self.tracker: Tracker = Tracker(snooze=self.ttf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.ema(length=self.slow_ema, append=True)
            candles.ta.ema(length=self.fast_ema, append=True)
            candles.rename(inplace=True, **{f"EMA_{self.fast_ema}": "fast", f"EMA_{self.slow_ema}": "slow"})

            fas = candles.ta_lib.above(candles.fast, candles.slow)  # fast above slow
            fbs = candles.ta_lib.below(candles.fast, candles.slow)  # fast below slow
            caf = candles.ta_lib.above(candles.close, candles.fast)  # close above fast
            cbf = candles.ta_lib.below(candles.close, candles.fast)  # close below fast

            current = candles[-2]
            if fas.iloc[-1] and caf.iloc[-1] and current.is_bullish():
                self.tracker.update(trend="bullish")

            elif fbs.iloc[-1] and cbf.iloc[-1] and current.is_bearish():
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging", snooze=self.ttf.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend\n")
            self.tracker.update(snooze=self.ttf.time, order_type=None)

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.update(new=False, order_type=None)
                return

            self.tracker.update(new=True, entry_time=current)
            candles.ta.ema(length=self.entry_ema, append=True)
            candles.rename(**{f"EMA_{self.entry_ema}": "ema"})
            cae = candles.ta_lib.cross(candles.close, candles.ema)
            cbe = candles.ta_lib.cross(candles.close, candles.ema, above=False)
            candles = candles[-24: -1]
            if self.tracker.bullish and cae.iloc[-2]:
                sl = find_bullish_fractal(candles)
                self.parameters['used_fractal'] = True if sl is not None else False
                sl = sl.low if sl is not None else candles.low.min()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl)
            elif self.tracker.bearish and cbe.iloc[-2]:
                sl = find_bearish_fractal(candles)
                self.parameters['used_fractal'] = True if sl is not None else False
                sl = sl.high if sl is not None else candles.high.max()
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL, sl=sl)
            else:
                self.tracker.update(snooze=self.etf.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.confirm_trend\n")
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
                    await self.sleep(self.trend_time_frame.time)