from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, Config, Order, TradeAction

from ..utils import calc_loss

logger = getLogger(__name__)


async def trail_sl(*, position: TradePosition):
    try:
        config = Config()
        order = config.state['losing'][position.ticket]
        trail_start = order['trail_start']
        last_profit = order['last_profit']
        sym = Symbol(name=position.symbol)
        await sym.init()
        loss = calc_loss(sym=sym, open_price=position.price_open, close_price=position.sl, volume=position.volume,
                         order_type=position.type)
        trail_loss = round(trail_start * loss, 2)
        trailing = order['trailing']
        if trailing and position.profit < last_profit and position.profit <= trail_loss:
            await modify_sl(position=position, sym=sym, order=order)
    except Exception as exe:
        logger.error(f'Trailing stop loss for {position.symbol}:{position.ticket} failed due to {exe}')


async def modify_sl(*, position: TradePosition, sym: Symbol, order: dict, extra: float = 0.0, tries: int = 4):
    try:
        config = Config()
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        loss = calc_loss(sym=sym, open_price=position.price_open, close_price=position.sl, volume=position.volume,
                         order_type=position.type)
        trail = order['trail']
        trail = trail / abs(loss)
        full_points = int(abs(position.price_open - position.sl) / sym.point)
        sl_points = full_points * trail
        sl_value = round(sl_points * sym.point, sym.digits)
        if position.type == OrderType.BUY:
            sl = position.sl - sl_value
            assert sl < position.sl
        else:
            sl = position.sl + sl_value
            assert sl > position.sl

        loss = calc_loss(sym=sym, open_price=position.price_open, close_price=sl, volume=position.volume,
                         order_type=position.type)
        sl_limit = order['sl_limit']
        if abs(loss) > sl_limit:
            closer = config.state['fixed_closer'][position.ticket]
            closer['close'] = True
            closer['cut_off'] = sl_limit
            order['trailing'] = False
        trade_order = Order(position=position.ticket, sl=sl, tp=position.tp, action=TradeAction.SLTP)
        res = await trade_order.send()
        if res.retcode == 10009:
            order['last_profit'] = position.profit
            logger.info(f"Trailing stop loss for {position.symbol}:{position.ticket} successful. New loss is {loss}")
        elif res.retcode == 10016 and tries > 0:
            await modify_sl(position=position, sym=sym, order=order, extra=extra + 0.01, tries=tries - 1)
        else:
            logger.error(f"Trailing stop loss failed due to {res.comment} for {position.symbol}:{position.ticket}")
    except AssertionError:
        pass
    except Exception as exe:
        logger.error(f'Trailing stop loss failed due to {exe} for {position.symbol}:{position.ticket}')
        return False
