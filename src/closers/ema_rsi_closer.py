from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame

logger = getLogger(__name__)


async def ema_rsi_closer(*, position: TradePosition, parameters: dict):
    try:
        positions = Positions()
        sym = Symbol(name=position.symbol)
        await sym.init()
        tf = parameters.get('etf', parameters.get('ttf', TimeFrame.M15))
        tcc = parameters['tcc']
        cot = int(position.time)
        # rsi_level = parameters['rsi_level']
        order_type = parameters['order_type']
        candles = await sym.copy_rates_from_pos(count=tcc, timeframe=tf)
        candles.ta.ema(length=parameters['first_ema'], append=True)
        candles.ta.ema(length=parameters['second_ema'], append=True)
        candles.ta.rsi(append=True)
        candles.rename(**{f"EMA_{parameters['first_ema']}": "first", f"EMA_{parameters['second_ema']}": "second",
                          "RSI_14": "rsi"})
        candles['time'] = candles.time.astype(int)
        start = candles.data.where(candles.data.time >= cot).dropna().index[0]
        candles = candles[start:]
        if order_type == OrderType.BUY:
            fxs = candles.ta_lib.cross(candles.first, candles.second, above=False)
            if any(fxs):
                await positions.close_by(position)
                logger.info(f"Closed trade {position.ticket}")
        elif order_type == OrderType.SELL:
            fxs = candles.ta_lib.cross(candles.first, candles.second, above=True)
            if any(fxs):
                await positions.close_by(position)
                logger.info(f"Closed trade {position.ticket}")
    except Exception as exe:
        logger.error(f'An error occurred in function ema_rsi_closer {exe}')
