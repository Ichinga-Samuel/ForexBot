import asyncio
from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, OrderSendResult, OrderError

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
        order.hedge_order = False
        order.hedged = True
        order.hedger_params |= {'hedge_point': position.profit}
        hedge = OpenOrder(**(order.data | {'ticket': res.order, 'check_profit': False, 'track_profit': False,
                                           'track_loss': False, 'use_exit_signal': False}))

        order.hedged_order = hedge
        hedge.track_profit_params |= {'start_trailing': False, 'previous_profit': 0}
        hedge.config.state['tracked_orders'][hedge.ticket] = hedge
        req = res.request
        profit = calc_profit(sym=sym, open_price=req.price, close_price=req.tp, volume=req.volume, order_type=req.type)
        hedge.expected_profit = profit
        loss = calc_profit(sym=sym, open_price=req.price, close_price=req.sl, volume=req.volume, order_type=req.type)
        hedge.expected_loss = loss
    except Exception as exe:
        logger.error(f'An error occurred in function hedge_position {exe.traceback}')


async def make_hedge(*, position: TradePosition, hedge_params: dict) -> OrderSendResult:
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
        logger.info(f"Hedged {position.ticket} for {position.symbol} at {position.profit} with {res.order}")
        return res
    else:
        raise OrderError(f"Could not hedge {position.ticket} for {position.symbol} with {res.comment}")


async def track_hedge(*, order: OpenOrder):
    try:
        orders = order.config.state['tracked_orders']
        hedge_order = order.hedged_order
        pos = Positions()
        main_ticket, hedge_ticket = order.ticket, hedge_order.ticket
        main_pos, hedge_pos = await asyncio.gather(pos.position_get(ticket=main_ticket),
                                                   pos.position_get(ticket=hedge_ticket),
                                                   return_exceptions=True)
        if main_pos is None and hedge_pos is None:
            orders.pop(main_ticket, None)
            orders.pop(hedge_ticket, None)
            return

        if isinstance(main_pos, TradePosition):
            hedge_close = order.hedger_params['hedge_close']
            if main_pos.profit >= hedge_close:
                if isinstance(hedge_pos, TradePosition):
                    await pos.close_by(hedge_pos)
                    logger.info(f"Closed {hedge_pos.ticket}:{order.ticket}@{hedge_pos.profit}:{main_pos.profit}")
                    orders.pop(hedge_ticket, None)
                    order.check_profit = True
                    order.check_profit_params |= {'close': True, 'check_point': -1}
        else:
            if isinstance(hedge_pos, TradePosition):
                if hedge_pos.profit > 0:
                    adjust = hedge_order.check_profit_params['hedge_adjust']
                    check_point = hedge_pos.profit * adjust
                    hedge_order.track_profit = True
                    hedge_order.track_profit_params |= {'start_trailing': True}
                    hedge_order.check_profit_params |= {'close': True, 'check_point': check_point,
                                                        'use_check_points': True}
                    hedge_order.check_profit = True
                else:
                    await pos.close_by(hedge_pos)
                    logger.info(f"Closed {hedge_pos.ticket}:{order.ticket}@{hedge_pos.profit}")
                    orders.pop(hedge_ticket, None)
    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge {exe}')
