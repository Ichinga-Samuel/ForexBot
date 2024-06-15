from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, OrderSendResult

from ..utils.order_utils import calc_profit
from .track_order import OpenOrder

logger = getLogger(__name__)


async def atr_trailer(*, order: OpenOrder):
    try:
        position = order.position
        params = order.track_profit_params
        previous_profit = params['previous_profit']
        expected_profit = order.expected_profit
        trail_start = params['trail_start'] * expected_profit
        start_trailing = params['start_trailing']
        if start_trailing and (position.profit >= max(trail_start, previous_profit)):
            await modify_stops(order=order)
    except Exception as exe:
        logger.error(f"{exe}@{exe.__traceback__.tb_lineno} in atr_trailer for {order.position.symbol}:{order.ticket}")


async def modify_stops(*, order: OpenOrder, extra: float = 0.0, tries: int = 4):
    try:
        position = await Positions().position_get(ticket=order.position.ticket)
        params = order.strategy_parameters
        tp_params = order.track_profit_params
        symbol = Symbol(name=position.symbol)
        await symbol.init()
        etf = params['tptf']
        ecc = params['tpcc']
        atr = params.get('atr_length', 14)
        atr_factor = params.get('atr_factor', 0.75)
        candles = await symbol.copy_rates_from_pos(timeframe=etf, count=ecc)
        candles.ta.atr(append=True, length=atr)
        candles.rename(inplace=True, **{f'ATRr_{atr}': 'atr'})
        current = candles[-1]
        tick = await symbol.info_tick()
        expected_profit = order.expected_profit
        extend_start = tp_params['extend_start']

        min_points = symbol.trade_stops_level + symbol.spread * (1 + extra)
        min_value = round(min_points * symbol.point, symbol.digits)
        atr_value = current.atr * atr_factor
        if atr_value < min_value:
            atr_value = min_value
            logger.warning(f"Minimum stop levels used for {position.symbol} {current.atr=}{atr_factor=} in atr_trailer")
        change_tp = False
        change_sl = False
        if position.type == OrderType.BUY:
            sl = tick.ask - atr_value
            if sl > max(position.sl, position.price_open):
                sl = round(sl, symbol.digits)
                change_sl = True
            else:
                sl = position.sl
            if position.profit / expected_profit >= extend_start:
                tp = round(position.tp + current.atr * atr_factor, symbol.digits)
                change_tp = True
            else:
                tp = position.tp
        else:
            sl = tick.bid + atr_value
            if sl < min(position.sl, position.price_open):
                sl = round(sl, symbol.digits)
                change_sl = True
            else:
                sl = position.sl

            if position.profit / expected_profit >= extend_start:
                tp = round(position.tp - current.atr * atr_factor, symbol.digits)
                change_tp = True
            else:
                tp = position.tp

        if change_tp is False and change_sl is False:
            return

        res = await send_order(position=position, sl=sl, tp=tp)
        if res.retcode == 10009:
            order.track_profit_params['previous_profit'] = position.profit
            captured_profit = calc_profit(sym=symbol, open_price=position.price_open, close_price=sl,
                                          volume=position.volume, order_type=position.type)
            logger.info(f"Changed stop_levels for"
                         f"{position.symbol}:{position.ticket}@{position.profit=}@{captured_profit=}")
            if change_tp:
                new_profit = calc_profit(sym=symbol, open_price=position.price_open, close_price=tp,
                                         volume=position.volume, order_type=position.type)
                order.expected_profit = new_profit
                logger.info(f"Changed expected profit to {new_profit} for"
                             f"{position.symbol}:{position.ticket}@{position.profit=}@{captured_profit=}")

        elif res.retcode == 10016 and tries > 0:
            await modify_stops(order=order, extra=(extra + 0.01), tries=tries - 1)
        else:
            logger.error(f"Unable to place order due to {res.comment} for {position.symbol}:{position.ticket}")
    except Exception as exe:
        logger.error(f"atr_trailer failed due to {exe}@{exe.__traceback__.tb_lineno}"
                     f" for {order.position.symbol}:{order.position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res
