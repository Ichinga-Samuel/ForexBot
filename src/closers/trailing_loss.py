from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, Config, Order, TradeAction

from ..utils import calc_loss

logger = getLogger(__name__)


async def trail_sl(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('losing', {}).setdefault(position.ticket, {})
        trail_start = order.setdefault('trail_start', 0.75)
        last_profit = order.setdefault('last_profit', 0)
        sym = Symbol(name=position.symbol)
        await sym.init()
        loss = calc_loss(sym=sym, open_price=position.price_open, close_price=position.sl, volume=position.volume,
                         order_type=position.type)
        trail_loss = round(trail_start * loss, 2)
        if position.profit < last_profit and position.profit <= trail_loss:
            await modify_sl(position=position, sym=sym)
    except Exception as exe:
        logger.error(f'Trailing stop loss for {position.symbol}:{position.ticket} failed due to {exe}')


async def modify_sl(*, position: TradePosition, sym: Symbol, extra=0.0, tries=4):
    try:
        config = Config()
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        remaining_points = int(abs(position.price_current - position.sl) / sym.point)
        stops_level = int(sym.trade_stops_level + sym.spread * (1 + extra))
        sl_points = remaining_points * 2
        sl_points = max(sl_points, stops_level)
        sl_value = round(sl_points * sym.point, sym.digits)
        if position.type == OrderType.BUY:
            sl = position.price_current - sl_value
            assert sl < position.sl
        else:
            sl = position.price_current + sl_value
            assert sl > position.sl

        order = Order(position=position.ticket, sl=sl, tp=position.tp, action=TradeAction.SLTP)
        res = await order.send()
        if res.retcode == 10009:
            config.state['loss'][position.ticket]['last_profit'] = position.profit
            loss = calc_loss(sym=sym, open_price=position.price_open, close_price=sl, volume=position.volume,
                             order_type=position.type)
            prev_loss = calc_loss(sym=sym, open_price=position.price_open, close_price=position.sl,
                                  volume=position.volume, order_type=position.type)
            logger.warning(f"Trailing loss {position.symbol}:{position.ticket} {loss=} {prev_loss=}")
        elif res.retcode == 10016 and tries > 0:
            await modify_sl(position=position, sym=sym, extra=extra + 0.01, tries=tries - 1)
        else:
            logger.error(f"Trailing stop loss failed due to {res.comment} for {position.symbol}:{position.ticket}")
    except AssertionError:
        pass
    except Exception as exe:
        logger.error(f'Trailing stop loss failed due to {exe} for {position.symbol}:{position.ticket}')
        return False
