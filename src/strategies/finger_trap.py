import asyncio
import logging

from aiomql import Tracker, ForexSymbol, TimeFrame, OrderType, Sessions, Strategy, Candles, Trader

from ..traders.sp_trader import SPTrader
from ..closers.ema_closer import ema_closer
logger = logging.getLogger(__name__)


class FingerTrap(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    fast_ema: int
    slow_ema: int
    entry_ema: int
    ecc: int
    tcc: int
    trend_interval: TimeFrame = TimeFrame.M15
    entry_interval: TimeFrame = TimeFrame.M2
    timeout: TimeFrame = TimeFrame.H2
    trader: Trader
    tracker: Tracker
    trend_candles: Candles
    trend: int = 24
    parameters = {"fast_ema": 8, "slow_ema": 34, "etf": TimeFrame.M5, 'exit_function': ema_closer,
                  "ttf": TimeFrame.H1, "entry_ema": 5, "tcc": 720, "ecc": 1440, "exit_ema": 5,
                  "excc": 720, "exit_timeframe": TimeFrame.H1, "tptf": TimeFrame.H1, "tpcc": 720,
                 "atr_factor": 0.25}

    def __init__(self, *, symbol: ForexSymbol, params: dict | None = None, trader: Trader = None,
                 sessions: Sessions = None, name: str = 'FingerTrap'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        ram = RAM(risk_to_reward=1)             
        self.trader = trader or SPTrader(symbol=self.symbol, track_loss=False, hedge_order=False,
                                         track_profit_params={"trail_start": 0.5}, ram=ram)
        self.tracker: Tracker = Tracker(snooze=self.ttf.time)

    async def check_trend(self):
        try:
            candles: Candles = await self.symbol.copy_rates_from_pos(timeframe=self.ttf, count=self.tcc) 
            if (current := candles[-1].time) < self.tracker.trend_time:
                self.tracker.update(new=False, order_type=None)
                return

            self.tracker.update(new=True, trend_time=current, order_type=None)
            candles.ta.ema(length=self.slow_ema, append=True)
            candles.ta.ema(length=self.fast_ema, append=True)
            candles.ta.adx(append=True, mamode='ema')
            candles.rename(inplace=True, **{f"EMA_{self.fast_ema}": "fast", f"EMA_{self.slow_ema}": "slow",
                                            "ADX_14": "adx", "DMP_14": "dmp", "DMN_14": "dmn"})  

            candles['caf'] = candles.ta_lib.above(candles.close, candles.fast, asint=False)
            candles['fas'] = candles.ta_lib.above(candles.fast, candles.slow, asint=False)

            candles['fbs'] = candles.ta_lib.below(candles.fast, candles.slow, asint=False)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.fast, asint=False)

            current = candles[-1]
            prev = candles[-2]
            uptrend = current.caf and current.fas and current.adx > 25 and current.dmp > current.dmn
            downtrend = current.fbs and current.cbf and current.adx > 25 and current.dmn > current.dmp
            higher_high = current.high > prev.high or current.low > prev.low
            lower_low = current.low < prev.low or current.high < prev.low

            if current.is_bullish() and uptrend and higher_high:
                candles['cxf'] = candles.ta_lib.cross(candles.close, candles.fast, asint=False)
                self.trend_candles = candles
                self.tracker.update(trend="bullish")
            elif current.is_bearish() and downtrend and lower_low:
                candles['cxf'] = candles.ta_lib.cross(candles.close, candles.fast, asint=False, above=False)
                self.trend_candles = candles
                self.tracker.update(trend="bearish")
            else:
                self.tracker.update(trend="ranging", snooze=self.trend_interval.time, order_type=None)
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.trend_interval.time, order_type=None)

    async def confirm_trend(self):
        try:
            candles = await self.symbol.copy_rates_from_pos(timeframe=self.etf, count=self.ecc)
            if (current := candles[-1].time) < self.tracker.entry_time:
                self.tracker.update(new=False, order_type=None)  
                return

            self.tracker.update(new=True, entry_time=current, order_type=None)
            candles.ta.ema(length=self.entry_ema, append=True)
            candles.rename(**{f"EMA_{self.entry_ema}": "ema"})
            candles['cxe'] = candles.ta_lib.cross(candles.close, candles.ema, asint=False)
            candles['exc'] = candles.ta_lib.cross(candles.close, candles.ema, above=False, asint=False)

            current = candles[-1]
            if self.tracker.bullish and current.cxe:
                for candle in reversed(self.trend_candles):
                    if candle.cxf:
                        sl = candle.low
                        break
                else:
                    sl = candles[-2].low
                tp = current.close + (current.close - sl) * self.trader.ram.risk_to_reward
                price = current.close
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.BUY, sl=sl, tp=tp, price=price)
            elif self.tracker.bearish and current.exc:
                for candle in reversed(self.trend_candles):
                    if candle.cxf:
                        sl = candle.high
                        break
                else:
                    sl = candles[-2].low
                tp = current.close - (sl - current.close) * self.trader.ram.risk_to_reward
                price = current.close
                self.tracker.update(snooze=self.timeout.time, order_type=OrderType.SELL, tp=tp, sl=sl, price=price)
            else:
                self.tracker.update(snooze=self.entry_interval.time, order_type=None)
        except Exception as err:
            logger.error(f"{err} for {self.symbol} in {self.__class__.__name__}.confirm_trend")
            self.tracker.update(snooze=self.entry_interval.time, order_type=None)

    async def watch_market(self):
        await self.check_trend()
        if not self.tracker.ranging:
            await self.confirm_trend()

    async def trade(self):
        print(f"Trading {self.symbol} with {self.name}")
        async with self.sessions as sess:
            await self.sleep(self.tracker.snooze)
            while True:
                await sess.check()
                try:
                    await self.watch_market()
                    if self.tracker.new is False:
                        await asyncio.sleep(2)
                        continue
                    if self.tracker.order_type is None:
                        await self.sleep(self.tracker.snooze)
                        continue
                    await self.trader.place_trade(order_type=self.tracker.order_type, parameters=self.parameters,
                                                  sl=self.tracker.sl, tp=self.tracker.tp)
                    await self.sleep(self.tracker.snooze)
                except Exception as err:
                    logger.error(f"{err} For {self.symbol} in {self.__class__.__name__}.trade")
                    await self.sleep(self.interval.time)
