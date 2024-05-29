from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from ..utils.tracker import Tracker
from ..closers.adx_closer import adx_closer
from ..traders.sp_trader import SPTrader

logger = getLogger(__name__)


class FFATR(Strategy):
    htf: TimeFrame
    ttf: TimeFrame
    atr_multiplier: int
    atr_factor: int
    atr_length: int
    first_ema: int
    second_ema: int
    trend_ema: int
    parameters: dict
    tcc: int
    hcc: int
    trader: Trader
    tracker: Tracker
    lower_interval: TimeFrame
    higher_interval: TimeFrame
    timeout: TimeFrame = TimeFrame.H4
    parameters = {"first_ema": 10, "second_ema": 21, "trend_ema": 50, "ttf": TimeFrame.H1, "tcc": 720,
                  'exit_function': adx_closer, "htf": TimeFrame.H4, "hcc": 180, "exit_timeframe": TimeFrame.H1,
                  "ecc": 720, "adx": 14, "atr_multiplier": 2, "atr_factor": 0.25, "atr_length": 14,
                  "excc": 720, "lower_interval": TimeFrame.M15, "higher_interval": TimeFrame.H2, "etf": TimeFrame.H1}

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'FFATR'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        self.trader = trader or SPTrader(symbol=self.symbol, hedge_order=True, track_loss=True, use_exit_signal=True)
        self.tracker: Tracker = Tracker(snooze=self.ttf.time)

    async def check_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc)
            c_candles = await self.symbol.copy_rates_from_pos(timeframe=self.htf, count=self.hcc)
            if (current := candles[-1].time) < self.tracker.trend_time:
                self.tracker.update(new=False, order_type=None)
                return
            self.tracker.update(new=True, trend_time=current, order_type=None)
            c_candles.ta.ema(length=self.trend_ema, append=True)
            c_candles.ta.adx(append=True)
            c_candles.rename(inplace=True, **{f"EMA_{self.trend_ema}": "ema", "ADX_14": "adx", "DMP_14": "dmp",
                                              "DMN_14": "dmn"})
            c_candles['cae'] = c_candles.ta_lib.above(c_candles.close, c_candles.ema, asint=False)
            c_candles['cbe'] = c_candles.ta_lib.below(c_candles.close, c_candles.ema, asint=False)

            c_current = c_candles[-1]
            if c_current.cae and c_current.adx >= 25 and c_current.dmp > c_current.dmn:
                self.tracker.update(trend="bullish")
            elif c_current.cbe and c_current.adx >= 25 and c_current.dmn > c_current.dmp:
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging", snooze=self.higher_interval.time, order_type=None)
                return

            candles.ta.ema(length=self.first_ema, append=True)
            candles.ta.ema(length=self.second_ema, append=True)
            candles.ta.atr(append=True)
            candles.ta.adx(append=True)
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            "ADX_14": "adx", "DMP_14": "dmp", "DMN_14": "dmn",
                                            f"ATRr_{self.atr_length}": "atr"})
            candles['pxn'] = candles.ta_lib.cross(candles.dmp, candles.dmn, asint=False)
            candles['nxp'] = candles.ta_lib.cross(candles.first, candles.second, asint=False)
            candles['caf'] = candles.ta_lib.above(candles.close, candles.first, asint=False)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second, asint=False)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first, asint=False)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second, asint=False)

            current = candles[-1]
            prev = candles[-2]
            above = current.caf and current.fas and current.is_bullish()
            below = current.cbf and current.fbs and current.is_bearish()
            higher_high = current.high > prev.high or current.low > prev.low
            lower_low = current.low < prev.low or current.high < prev.high
            up_trend = current.adx >= 25 and current.dmp > current.dmn and higher_high and above
            down_trend = current.adx >= 25 and current.dmn > current.dmp and lower_low and below

            if self.tracker.bullish and up_trend:
                for candle in reversed(candles):
                    if candle.pxn:
                        sl = candle.low
                        break
                else:
                    sl = current.low - (self.atr_multiplier * current.atr)

                tp = current.close + (current.close - sl) * self.trader.ram.risk_to_reward
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.BUY, sl=sl, tp=tp)

            elif True or (self.tracker.bearish and down_trend):
                for candle in reversed(candles):
                    if candle.nxp:
                        sl = candle.high
                        break
                else:
                    sl = current.high + (self.atr_multiplier * current.atr)
                tp = current.close - (sl - current.close) * self.trader.ram.risk_to_reward
                slp = self.symbol.trade_stops_level + (self.symbol.spread * 2)
                slv = slp * self.symbol.point
                sl = current.close + slv
                tp = current.close - slv
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.SELL, sl=sl, tp=tp)
            else:
                self.tracker.update(trend="ranging", snooze=self.lower_interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.lower_interval.time, order_type=None)

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            # await self.sleep(self.tracker.snooze)
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
                    await self.trader.place_trade(order_type=self.tracker.order_type, sl=self.tracker.sl,
                                                  tp=self.tracker.tp, parameters=self.parameters)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.tracker.snooze)
