from logging import getLogger
import asyncio

from aiomql import Symbol, Candles, Strategy, TimeFrame, Sessions, OrderType, Tracker, SimpleTrader

logger = getLogger(__name__)


class ADI2(Strategy):
    tracker: Tracker
    ecc: int
    tcc: int
    ttf: TimeFrame
    etf: TimeFrame
    slow_sma: int
    fast_sma: int
    rsi_period: int
    rsi_upper: int
    rsi_lower: int
    _parameters = {"ecc": 288, "tcc": 24, "ttf": TimeFrame.H1, "etf": TimeFrame.M5, 'slow_sma': 20, 'fast_sma': 5,
                   'rsi_period': 14, 'rsi_upper': 65, 'rsi_lower': 35}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None, name: str = "ADIStrategy",
                 trader=None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or SimpleTrader(symbol=self.symbol)

    async def check_trend(self):
        try:
            candles: Candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.new = False
                return
            self.tracker.update(new=True, trend_time=current)
            candles.ta.ad(volume="tick_volume", append=True)
            candles.ta.rsi(close="AD", length=self.rsi_period, append=True)
            candles.rename(**{f'RSI_{self.rsi_period}': 'rsi'})
            rsi = sum(c.rsi for c in candles[-4:-1]) / 3
            if 0 < rsi <= self.rsi_lower:
                self.tracker.update(trend="bullish")
            elif self.rsi_upper <= rsi <= 100:
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging")
        except Exception as err:
            logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.check_trend")
            return

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if not ((current := candles[-1].time) >= self.tracker.entry_time):
                self.tracker.new = False
                return
            self.tracker.update(new=True, entry_time=current)
            candles.ta.sma(length=self.fast_sma, append=True)
            candles.ta.sma(length=self.slow_sma, append=True)
            candles.rename(**{f'SMA_{self.fast_sma}': 'fast_sma', f'SMA_{self.slow_sma}': 'slow_sma'})
            above = candles.ta_lib.cross(candles["fast_sma"], candles["slow_sma"])
            below = candles.ta_lib.cross(candles["fast_sma"], candles["slow_sma"], above=False)
            if self.tracker.bullish and above.iloc[-2]:
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY)
            elif self.tracker.bearish and below.iloc[-2]:
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL)
            else:
                self.tracker.update(snooze=self.etf.time, order_type=None)
        except Exception as err:
            logger.error(f"Error: {err}\t Symbol: {self.symbol} in {self.__class__.__name__}.confirm_trend")
            return

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