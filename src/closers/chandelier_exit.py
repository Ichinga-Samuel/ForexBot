from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, OrderSendResult, TimeFrame

from ..utils.order_utils import calc_profit
from .track_order import OpenOrder

logger = getLogger(__name__)


async def chandelier_trailer(*, order: OpenOrder):
    try:
        position = order.position
        params = order.track_profit_params
        previous_profit = params['previous_profit']
        expected_profit = order.target_profit or order.expected_profit
        trail_start = params['trail_start'] * expected_profit
        start_trailing = params['start_trailing']
        if start_trailing and (position.profit >= max(trail_start, previous_profit)):
            await chandelier(order=order)
    except Exception as exe:
        logger.error(f"{exe}@{exe.__traceback__.tb_lineno} in chandelier_trailer for "
                     f"{order.position.symbol}:{order.ticket}")


async def chandelier(*, order: OpenOrder):
    try:
        position = await Positions().position_get(ticket=order.position.ticket)
        tp_params = order.track_profit_params
        st_params = order.strategy_parameters
        symbol = Symbol(name=position.symbol)
        await symbol.init()
        atr = 14
        atr_factor = st_params.get('atr_factor', 2)
        ce_period = tp_params['ce_period']
        candles = await symbol.copy_rates_from_pos(timeframe=TimeFrame.D1, count=60)
        candles.ta.atr(append=True, length=atr)
        candles.rename(inplace=True, **{f'ATRr_{atr}': 'atr'})
        p_candles = candles[-ce_period:]
        current = p_candles[-1]
        expected_profit = order.target_profit or order.expected_profit
        extend_start = tp_params['extend_start']
        change_sl = change_tp = False
        trail_start = tp_params['trail_start']
        if position.type == OrderType.BUY:
            sl = max(candles.high.iloc[-ce_period:]) - atr_factor * current.atr
            if sl > position.sl and (trail_start == 0 or sl > position.price_open):
                sl = round(sl, symbol.digits)
                change_sl = True
            else:
                sl = position.sl
            if position.profit / order.expected_profit >= extend_start:
                tp = round(position.tp + current.atr, symbol.digits)
                order.check_profit_params['close'] = True
                order.check_profit_params['check_point'] = position.profit * 0.90
                change_tp = True
            else:
                tp = position.tp
        else:
            sl = min(candles.low.iloc[-ce_period:]) + atr_factor * current.atr
            if sl < position.sl and (trail_start == 0 or sl < position.price_open):
                sl = round(sl, symbol.digits)
                change_sl = True
            else:
                sl = position.sl

            if position.profit / order.expected_profit >= extend_start:
                tp = round(position.tp - current.atr, symbol.digits)
                order.check_profit_params['close'] = True
                order.check_profit_params['check_point'] = position.profit * 0.90
                change_tp = True
            else:
                tp = position.tp

        if change_tp is False and change_sl is False:
            return
        res = await send_order(position=position, sl=sl, tp=tp)
        if res.retcode == 10009:
            order.track_profit_params['previous_profit'] = position.profit
            taken_profit = calc_profit(sym=symbol, open_price=position.price_open, close_price=sl,
                                       volume=position.volume, order_type=position.type)
            captured_profit = max(taken_profit, 0)
            old_loss = order.expected_loss
            order.expected_loss = min(0, taken_profit)
            logger.info(f"Track sl:tp for {position.symbol}:{position.ticket}@{position.profit=}@{captured_profit=}"
                        f"@{order.expected_loss=}@{old_loss=}")
            if change_tp:
                new_profit = calc_profit(sym=symbol, open_price=position.price_open, close_price=tp,
                                         volume=position.volume, order_type=position.type)
                order.expected_profit = new_profit
                logger.info(f"Extend profit to {new_profit}4{position.symbol}:{position.ticket}")
        else:
            logger.error(f"Unable to place order due to {res.comment} for {position.symbol}:{position.ticket}")
    except Exception as exe:
        logger.error(f"chandelier_trailer failed due to {exe}@{exe.__traceback__.tb_lineno}"
                     f" for {order.position.symbol}:{order.position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res
