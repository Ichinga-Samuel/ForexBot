import asyncio
from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, OrderSendResult

from .track_order import OpenOrder
from ..utils.order_utils import calc_profit

logger = getLogger(__name__)


async def hedge_position(*, order: OpenOrder):
    try:
        position = await Positions().position_get(ticket=order.ticket)
        hedge_params = order.hedger_params
        hedge_point = hedge_params['hedge_point']
        if position.profit > hedge_point * order.expected_loss:
            return
        sym = Symbol(name=position.symbol)
        await sym.init()
        res = await make_hedge(position=position, hedge_params=hedge_params)
        if res is None:
            return
        order.hedge_order = False
        order.hedged = True
        data = order.data | {'ticket': res.order, 'check_profit': False, 'track_profit': False,
                             'track_loss': False, 'use_exit_signal': False}
        hedge = OpenOrder(**data)
        hedge.hedged_order = order
        order.hedge = hedge
        order.hedger_params['hedge_point'] = position.profit
        hedge.track_profit_params |= {'start_trailing': False, 'previous_profit': 0}
        hedge.config.state['tracked_orders'][hedge.ticket] = hedge
        req = res.request
        profit = calc_profit(sym=sym, open_price=req.price, close_price=req.tp, volume=req.volume, order_type=req.type)
        hedge.expected_profit = profit
        loss = calc_profit(sym=sym, open_price=req.price, close_price=req.sl, volume=req.volume, order_type=req.type)
        hedge.expected_loss = loss
    except Exception as exe:
        logger.error(f'An error occurred in function hedge_position {exe}@{exe.__traceback__.tb_lineno} '
                     f'{order.ticket}{order.symbol}')


async def make_hedge(*, position: TradePosition, hedge_params: dict) -> OrderSendResult:
    try:
        osl = abs(position.sl - position.price_open)
        otp = abs(position.tp - position.price_open)

        tick = await Symbol(name=position.symbol).info_tick()
        price = tick.bid if position.type == OrderType.BUY else tick.ask

        if position.type == OrderType.BUY:
            sl = price + osl
            tp = price - otp
        else:
            sl = price - osl
            tp = price + otp

        order = Order(symbol=position.symbol, price=price, sl=sl, tp=tp, type=position.type.opposite,
                      volume=position.volume * hedge_params['hedge_vol'], comment=f"Rev{position.ticket}")
        res = await order.send()
        if res.retcode == 10009:
            return res
        logger.error(f"Could not hedge {position.ticket} for {position.symbol} with {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function make_hedge {exe}@{exe.__traceback__.tb_lineno}')


async def track_hedge(*, hedge: OpenOrder):
    try:
        orders = hedge.config.state['tracked_orders']
        hedged_order = hedge.hedged_order
        pos = Positions()
        hedged_ticket, hedge_ticket = hedged_order.ticket, hedge.ticket
        hedged_pos, hedge_pos = await asyncio.gather(pos.position_get(ticket=hedged_ticket),
                                                     pos.position_get(ticket=hedge_ticket), return_exceptions=True)
        if hedged_pos is None and hedge_pos is None:
            orders.pop(hedged_ticket, None)
            orders.pop(hedge_ticket, None)
            return

        if isinstance(hedged_pos, TradePosition):
            hedge_close = hedged_order.hedger_params['hedge_close']
            if hedged_pos.profit >= hedge_close:
                if isinstance(hedge_pos, TradePosition):
                    await pos.close_by(hedge_pos)
                    logger.info(f"Closed {hedge_pos.ticket}:{hedged_pos.ticket}@"
                                f"{hedge_pos.profit}:{hedged_pos.profit} hedged order in profit")
                orders.pop(hedge_ticket, None)
                hedged_order.check_profit = True
                hedged_order.check_profit_params |= {'close': True, 'check_point': -1}

        elif isinstance(hedge_pos, TradePosition):
            if hedge_pos.profit > 0:
                adjust = hedge.check_profit_params['hedge_adjust']
                check_point = hedge_pos.profit * adjust
                hedge.track_profit = True
                hedge.track_profit_params |= {'start_trailing': True}
                hedge.check_profit_params |= {'close': True, 'check_point': check_point, 'use_check_points': True}
                hedge.check_profit = True
            else:
                await pos.close_by(hedge_pos)
                logger.info(f"Closed {hedge_pos.ticket}:{hedged_order.ticket}@{hedge_pos.profit} hedge in loss")
                orders.pop(hedge_ticket, None)
    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge {exe}@{exe.__traceback__.tb_lineno}')
