from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, Order, TradeAction

from ..utils.order_utils import calc_loss
from .track_order import OpenOrder

logger = getLogger(__name__)


async def trail_sl(*, position: TradePosition, order: OpenOrder):
    try:
        print('Using Trailing Stop Loss')
        params = order.track_loss_params
        trail_start = params['trail_start']
        previous_profit = params['previous_profit']
        loss = params['expected_loss']
        trail_loss = round(trail_start * loss, 2) * -1
        trailing = params['trailing']
        if trailing and position.profit < previous_profit and position.profit <= trail_loss:
            await modify_sl(position=position, params=params)
    except Exception as exe:
        logger.error(f'Trailing stop loss for {position.symbol}:{position.ticket} failed due to {exe}')


async def modify_sl(*, position: TradePosition, params: dict, extra: float = 0.0, tries: int = 4):
    try:
        sym = Symbol(name=position.symbol)
        await sym.init()
        pos = Positions()
        position = await pos.position_get(ticket=position.ticket)
        trail = 1 - params['trail_start']
        full_points = abs(position.price_open - position.sl) / sym.point
        sl_points = full_points * trail
        sl_value = round(sl_points * sym.point, sym.digits)
        if position.type == OrderType.BUY:
            sl = position.sl - sl_value
        else:
            sl = position.sl + sl_value
        loss = calc_loss(sym=sym, open_price=position.price_open, close_price=sl, volume=position.volume,
                         order_type=position.type)
        trade_order = Order(position=position.ticket, sl=sl, tp=position.tp, action=TradeAction.SLTP)
        res = await trade_order.send()
        if res.retcode == 10009:
            params['previous_profit'] = position.profit
            params['expected_loss'] = abs(loss)
            logger.info(f"Trailing stop loss for {position.symbol}:{position.ticket} successful. New loss is {loss}")
        elif res.retcode == 10016 and tries > 0:
            await modify_sl(position=position, params=params, extra=extra + 0.01, tries=tries - 1)
        else:
            logger.error(f"Trailing stop loss failed due to {res.comment} for {position.symbol}:{position.ticket}")
    except Exception as exe:
        logger.error(f'Trailing stop loss failed due to {exe} for {position.symbol}:{position.ticket}')
