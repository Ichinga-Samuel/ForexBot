import asyncio
from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, OrderSendResult, OrderError

from .track_order import OpenOrder

logger = getLogger(__name__)


async def hedge_position(*, position: TradePosition, order: OpenOrder):
    try:
        position = await Positions().position_get(ticket=position.ticket)
        hedge_params = order.hedger_params
        # assert (not position.comment.startswith('Rev'))
        hedge_point = hedge_params['hedge_point']
        loss = hedge_params['loss']
        if position.profit <= hedge_point * -loss:
            sym = Symbol(name=position.symbol)
            await sym.init()
            res = await make_hedge(position=position, hedge_params=hedge_params)
            order.hedge_order = False
            hedge = OpenOrder(**(order.data | {'ticket': res.order}))
            order.hedged_order = hedge
            order.hedged = True
            hedge.track_profit_params |= {'start_trailing': False, 'previous_profit': 0}
            hedge.check_profit = False
            hedge.track_loss = False
            hedge.use_exit_signal = False
            position.config.state['order_tracker'][hedge.ticket] = hedge
            order.hedger_params |= {'hedge_point': position.profit}
    except Exception as exe:
        logger.error(f'An error occurred in function hedge {exe}')


async def make_hedge(*, position: TradePosition, hedge_params: dict) -> OrderSendResult:
    osl = abs(position.sl - position.price_open)
    otp = abs(position.tp - position.price_open)

    if position.type == OrderType.BUY:
        sl = position.price_open + osl
        tp = position.price_open - otp
    else:
        sl = position.price_open - osl
        tp = position.price_open + otp

    order = Order(symbol=position.symbol, price=position.price_current, sl=sl, tp=tp, type=position.type.opposite,
                  volume=position.volume * hedge_params['hedge_vol'], comment=f"Rev{position.ticket}")
    res = await order.send()
    if res.retcode == 10009:
        logger.info(f"Hedged {position.ticket} for {position.symbol} at {position.profit} with {res.order}")
        return res
    else:
        raise OrderError(f"Could not hedge {position.ticket} for {position.symbol} with {res.comment}")


async def track_hedge(*, position: TradePosition, order: OpenOrder):
    try:
        orders = position.config.state['tracked_orders']
        hedge_order = order.hedged_order
        pos = Positions()
        main_ticket, hedge_ticket = position.ticket, hedge_order.ticket
        main_pos, hedge_pos = await asyncio.gather(pos.position_get(ticket=main_ticket),
                                                   pos.position_get(ticket=hedge_ticket),
                                                   return_exceptions=True)
        if isinstance(main_pos, Exception) and isinstance(hedge_pos, Exception):
            orders.pop(main_ticket) if main_ticket in orders else ...
            orders.pop(hedge_ticket) if hedge_ticket in orders else ...
            return

        if isinstance(main_pos, TradePosition):
            hedge_cutoff = order.hedger_params['hedge_cutoff']

            if main_pos.profit >= hedge_cutoff:
                if isinstance(hedge_pos, TradePosition):
                    await pos.close_by(hedge_pos)
                    logger.info(f"Closed {hedge_pos.symbol}:{hedge_pos.comment} for {main_pos.symbol}{main_pos.ticket} "
                                f"at {hedge_pos.profit=}:{main_pos.profit=}")

                    orders.pop(hedge_ticket) if hedge_ticket in orders else ...
                    order.check_profit_params |= {'close': True, 'check_point': -1}

        else:
            if isinstance(hedge_pos, TradePosition):
                if hedge_pos.profit > 0:
                    adjust = hedge_order.hedger_params['adjust']
                    hedge_order.track_profit_params |= {'start_trailing': True}
                    hedge_order.check_profit_params |= {'close': True, 'check_point': hedge_pos.profit - adjust}
                    hedge_order.check_profit = True
                elif hedge_pos.profit <= 0:
                    await pos.close_by(hedge_pos)
                    logger.info(f"Closed {hedge_pos.symbol}:{hedge_pos.comment} at {hedge_pos.profit}")
                    orders.pop(hedge_ticket) if hedge_ticket in orders else ...
    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge {exe}')
