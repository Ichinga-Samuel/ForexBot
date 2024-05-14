from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, Config, OrderSendResult

from ..utils.sym_utils import calc_profit

logger = getLogger(__name__)


async def atr_trailer(*, position: TradePosition):
    try:
        config = Config()
        order = config.state['atr_trailer'][position.ticket]
        prev_profit = order['prev_profit']
        if position.profit < prev_profit:
            return
        await modify_stops(position=position, order=order)
    except Exception as err:
        logger.error(f"{err} in atr_trailer for {position.symbol}:{position.ticket}")


async def modify_stops(*, position: TradePosition, order: dict, extra: float = 0.0, tries: int = 4):
    try:
        position = await Positions().position_get(ticket=position.ticket)
        params = order['params']
        symbol = Symbol(name=position.symbol)
        await symbol.init()
        etf = params['etf']
        ecc = params['ecc']
        atr = params['atr_length']
        atr_factor = params['atr_factor']
        candles = await symbol.copy_rates_from_pos(timeframe=etf, count=ecc)
        candles.ta.atr(append=True, length=atr)
        candles.rename(inplace=True, **{f'ATRr_{atr}': 'atr'})
        current = candles[-1]
        tick = await symbol.info_tick()
        expected_profit = order['expected_profit']
        extend_profit = order['extend_profit']
        change_tp = False
        min_points = symbol.trade_stops_level + symbol.spread * (1 + extra)
        min_value = round(min_points * symbol.point, symbol.digits)

        if position.type == OrderType.BUY:
            atr_value = current.atr * atr_factor
            if atr_value < min_value:
                atr_value = min_value
                logger.warning(f"ATR value adjusted to {atr_value} for {symbol}")
            sl = tick.ask - atr_value
            assert sl > max(position.sl, position.price_open), f"current_sl={position.sl} >than new sl={sl} in long"
            if (position.profit / expected_profit) > extend_profit:
                profit_extension = 1 - extend_profit
                full_points = abs(position.price_open - position.tp) / symbol.point
                profit_extension = round(profit_extension * full_points * symbol.point, symbol.digits)
                tp = position.tp + profit_extension
                change_tp = True
            else:
                tp = position.tp
        else:
            atr_value = current.atr * atr_factor
            if atr_value < min_value:
                atr_value = min_value
                logger.warning(f"ATR value adjusted to {atr_value} for {symbol}")
            sl = tick.bid + atr_value
            assert sl < min(position.sl, position.price_open), f"current_sl={position.sl} <than new {sl=} in short"
            if (position.profit / expected_profit) > extend_profit:
                profit_extension = 1 - extend_profit
                full_points = abs(position.price_open - position.tp) / symbol.point
                profit_extension = round(profit_extension * full_points * symbol.point, symbol.digits)
                tp = position.tp + profit_extension
                change_tp = True
            else:
                tp = position.tp

        res = await send_order(position=position, sl=sl, tp=tp)
        if res.retcode == 10009:
            order['prev_profit'] = position.profit
            logger.warning(f"Changed Stop Levels for {position.symbol}:{position.ticket} from"
                           f" {position.sl}:{position.tp} to {sl=}{tp=}")
            if change_tp:
                new_profit = calc_profit(sym=symbol, open_price=position.price_open, close_price=position.tp,
                                         volume=position.volume, order_type=position.type)
                order['expected_profit'] = new_profit

        elif res.retcode == 10016 and tries > 0:
            await modify_stops(position=position, order=order, extra=(extra + 0.01), tries=tries - 1)
        else:
            logger.error(f"Unable to place order due to {res.comment} for {position.symbol}:{position.ticket}")
    except AssertionError as err:
        logger.error(f"atr_trailer failed due to {err} for {position.symbol}:{position.ticket}: AssertionError")
    except Exception as err:
        logger.error(f"atr_trailer failed due to {err} for {position.symbol}:{position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res
