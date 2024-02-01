from logging import getLogger
import asyncio
import warnings

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.ram import RAM
from ..traders.c_trader import CTrader
from ..utils.patterns import average_candle_length

logger = getLogger(__name__)


class MFI(Strategy):
    tracker: Tracker
    sma: int
    lower_mfi: int
    upper_mfi: int
    ttf: TimeFrame
    tcc: int
    parameters = {'sma': 9, 'lower_mfi': 30, 'upper_mfi': 70, 'ttf': TimeFrame.M15, 'tcc': 100}

    def __init__(self, *, symbol: Symbol, sessions: Sessions = None, params: dict = None, name: str = 'MFI',
                 trader: Trader = None):
        super().__init__(symbol=symbol, sessions=sessions, params=params, name=name)
        self.tracker = Tracker(snooze=self.ttf.time)
        self.trader = trader or CTrader(symbol=self.symbol, use_telegram=True, ram=RAM(risk_to_reward=1.333))

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if not ((current := candles[-1].time) >= self.tracker.trend_time):
                self.tracker.update(new=False, order_type=None)
                return

            self.tracker.update(new=True, trend_time=current)
            warnings.filterwarnings("ignore")
            candles.ta.mfi(volume='tick_volume', append=True, length=9)
            candles.rename(**{'MFI_9': 'mfi'})
            candles.ta.sma(close='mfi', length=self.sma, append=True)
            candles.rename(**{f'SMA_{self.sma}': 'sma'})
            above = candles.ta_lib.cross(candles.mfi, candles.sma)
            below = candles.ta_lib.cross(candles.mfi, candles.sma, above=False)
            mfi = candles[-1].mfi
            trend = candles[-8:]
            if mfi <= self.lower_mfi and above.iloc[-1]:
                sl = average_candle_length(trend)
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl)
            elif mfi >= self.upper_mfi and below.iloc[-1]:
                sl = average_candle_length(trend)
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL, sl=sl)
            else:
                self.tracker.update(trend="ranging", order_type=None, snooze=self.ttf.time)
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.check_trend\n")
            self.tracker.update(snooze=self.ttf.time, order_type=None)

    async def trade(self):
        logger.info(f"Trading {self.symbol} with {self.name}")
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, acl=self.tracker.sl,
                                                  parameters=self.parameters)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} For {self.symbol} in {self.__class__.__name__}.trade\n")
                    await self.sleep(self.ttf.time)