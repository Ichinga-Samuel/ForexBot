from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..utils.top_bottom import double_top, double_bottom
from ..traders.p_trader import PTrader

logger = getLogger(__name__)


class FingerADX(Strategy):
    ttf: TimeFrame
    ltf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    third_ema: int
    price_sma: int
    adx_cutoff: int
    parameters: dict
    tcc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M15
    timeout: TimeFrame = TimeFrame.H2
    parameters = {"first_ema": 8, "second_ema": 16, "third_ema": 32, "ttf": TimeFrame.H1, "tcc": 720, "price_sma": 50,
                  "adx_cutoff": 22, "ltf": TimeFrame.M5, "etf": TimeFrame.M30}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'FingerADX'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or PTrader(symbol=self.symbol)

        self.tracker: Tracker = Tracker(snooze=self.ttf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            if (current := candles[-1].time) < self.tracker.trend_time:
                self.tracker.update(new=False, order_type=None)
                return
            l_candles = await self.symbol.copy_rates_from_pos(timeframe=self.ltf, count=self.tcc)
            e_candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.tcc)
            self.tracker.update(new=True, trend_time=current, order_type=None)
            l_candles.ta.adx(append=True, mamode='ema')
            l_candles.rename(inplace=True, **{"ADX_14": "adx", "DMP_14": "dmp", "DMN_14": "dmn"})
            candles.ta.ema(length=self.first_ema, append=True)
            candles.ta.ema(length=self.second_ema, append=True)
            candles.ta.ema(length=self.third_ema, append=True)
            candles.ta.sma(close='close', length=self.price_sma, append=True)
            candles.ta.adx(append=True, mamode='ema')
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"ADX_14": "adx", f"SMA_{self.price_sma}": "sma",
                                            f"EMA_{self.third_ema}": "third", "DMP_14": "dmp", "DMN_14": "dmn"})

            candles['cas'] = candles.ta_lib.above(candles.close, candles.sma)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['sat'] = candles.ta_lib.above(candles.second, candles.third)
            candles['cbs'] = candles.ta_lib.below(candles.close, candles.sma)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles['sbt'] = candles.ta_lib.below(candles.second, candles.third)
            l_candles['pxn'] = l_candles.ta_lib.above(l_candles.dmp, l_candles.dmn)
            l_candles['nxp'] = l_candles.ta_lib.above(l_candles.dmn, l_candles.dmp)
            l_current = l_candles[-1]
            current = candles[-1]
            prev = candles[-2]
            prev_2 = candles[-3]
            e_prev = e_candles[-2]
            e_prev_2 = e_candles[-3]
            db = double_bottom(first=e_prev_2, second=e_prev)
            dt = double_top(first=e_prev_2, second=e_prev)

            higher_high = current.high > prev.high or current.low > prev.low and current.dmp > current.dmn and l_current.pxn
            lower_low = current.low < prev.low or current.high < prev.high and current.dmn > current.dmp and l_current.nxp
            uptrend = all([current.cas, current.fas, current.sat]) and current.adx >= self.adx_cutoff and db
            downtrend = all([current.cbs, current.fbs, current.sbt]) and current.adx >= self.adx_cutoff and dt

            if current.is_bullish() and uptrend and higher_high:
                sl = current.close - ((current.close - min(prev.low, prev_2.low)) * 2)
                tp = current.close + (current.close - sl) * self.trader.ram.risk_to_reward
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.BUY, sl=sl, tp=tp)

            elif current.is_bearish() and downtrend and lower_low:
                sl = current.close + ((max(prev.high, prev_2.high) - current.close) * 2)
                tp = current.close - (sl - current.close) * self.trader.ram.risk_to_reward
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.SELL, sl=sl, tp=tp)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters,
                                                  sl=self.tracker.sl, tp=self.tracker.tp)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
