from logging import getLogger
import asyncio

from aiomql import Symbol, Strategy, TimeFrame, Sessions, OrderType, Trader

from src.utils.tracker import Tracker
from src.utils.ram import RAM
from src.traders.sp_trader import SPTrader
from src.closers.adx_closer import adx_closer


logger = getLogger(__name__)


class ADXATR(Strategy):
    ttf: TimeFrame
    etf: TimeFrame
    first_ema: int
    second_ema: int
    price_sma: int
    parameters: dict
    tcc: int
    ecc: int
    trader: Trader
    tracker: Tracker
    interval: TimeFrame = TimeFrame.M15
    timeout: int = TimeFrame.H2
    atr_multiplier: float
    adx_cutoff: int
    atr_factor: float
    atr_length: int
    parameters = {"first_ema": 2, "second_ema": 5, "ttf": TimeFrame.H1, "tcc": 720, "price_sma": 50,
                  "atr_multiplier": 1.5, "adx_cutoff": 25, "atr_factor": 0.5, "atr_length": 14, "ecc": 720,
                  "etf": TimeFrame.H1, "excc": 720, "exit_function": adx_closer, "exit_timeframe": TimeFrame.H1
                  }

    def __init__(self, *, symbol: Symbol, params: dict | None = None, trader: Trader = None, sessions: Sessions = None,
                 name: str = 'ADXATR'):
        super().__init__(symbol=symbol, params=params, sessions=sessions, name=name)
        ram = RAM(min_amount=5, max_amount=100, risk_to_reward=1.5, risk=0.1)
        self.trader = trader or SPTrader(symbol=self.symbol, use_exit_signal=True, ram=ram, track_loss=True,
                                         hedge_order=True, hedger_params={"hedge_point": 0.75})
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
            candles.ta.sma(close='close', length=self.price_sma, append=True)
            candles.ta.adx(append=True)
            candles.ta.atr(append=True, length=self.atr_length)
            candles.rename(inplace=True, **{f"EMA_{self.first_ema}": "first", f"EMA_{self.second_ema}": "second",
                                            f"ADX_14": "adx", f"SMA_{self.price_sma}": "sma",
                                            f"ATRr_{self.atr_length}": "atr", "DMP_14": "dmp", "DMN_14": "dmn"})

            candles['cas'] = candles.ta_lib.above(candles.close, candles.sma)
            candles['caf'] = candles.ta_lib.above(candles.close, candles.first)
            candles['fas'] = candles.ta_lib.above(candles.first, candles.second)
            candles['pan'] = candles.ta_lib.above(candles.dmp, candles.dmn)

            candles['cbs'] = candles.ta_lib.below(candles.close, candles.sma)
            candles['cbf'] = candles.ta_lib.below(candles.close, candles.first)
            candles['fbs'] = candles.ta_lib.below(candles.first, candles.second)
            candles['nap'] = candles.ta_lib.above(candles.dmn, candles.dmp)

            current = candles[-1]
            prev = candles[-2]
            higher_high = current.high > prev.high
            lower_low = current.low < prev.low

            if (current.is_bullish() and current.pan and current.adx >= 25
                and all([current.cas, current.caf, current.fas]) and higher_high):
                sl = current.low - (current.atr * self.atr_multiplier)
                tp = current.close + (current.atr * self.atr_multiplier * self.trader.ram.risk_to_reward)
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.BUY, sl=sl, tp=tp)

            elif (current.is_bearish() and current.nap and current.adx >= 25
                  and all([current.cbs, current.cbf, current.fbs]) and lower_low):
                sl = current.high + (current.atr * self.atr_multiplier)
                tp = current.close - (current.atr * self.atr_multiplier * self.trader.ram.risk_to_reward)
                self.tracker.update(snooze=self.ttf.time, order_type=OrderType.SELL, sl=sl, tp=tp)
            else:
                self.tracker.update(trend="ranging", snooze=self.interval.time, order_type=None)
        except Exception as exe:
            logger.error(f"{exe} for {self.symbol} in {self.__class__.__name__}.check_trend")
            self.tracker.update(snooze=self.interval.time, order_type=None)

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
