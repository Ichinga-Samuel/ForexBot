from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config

logger = getLogger(__name__)


async def reverse_trade(*, position: TradePosition):
    try:
        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        config = Config()
        hedge = config.state.setdefault('hedge', {})
        revd = hedge.setdefault('reversed', {})
        reversals = hedge.setdefault('reversals', [])
        sym = Symbol(name=position.symbol)
        await sym.init()
        points = abs(position.sl - position.price_open) / sym.point
        tp_points = abs(position.tp - position.price_open) / sym.point
        diff = abs(position.sl - position.price_open)
        rev_price = position.price_open - (0.1 * diff) if position.type == OrderType.BUY else position.price_open + (0.1 * diff)
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        loss_per = (abs(position.price_open - price) / abs(position.price_open - position.sl))
        print(loss_per)
        if position.profit < 0 and loss_per <= 0.10:
            return
        print(f'Loss per: {position.symbol}')
        if position.type == OrderType.BUY:
            order_type = OrderType.SELL
            sl = tick.ask + (points * sym.point)
            tp = tick.ask - (tp_points * sym.point)
        else:
            order_type = OrderType.BUY
            sl = tick.bid - (points * sym.point)
            tp = tick.bid + (tp_points * sym.point)
        order = Order(type=order_type, symbol=sym, sl=sl, tp=tp, volume=position.volume, comment="Reversal")
        res = await order.send()
        if res.retcode == 10009:
            reversals.append(res.order)
            revd[position.ticket] = {'reverse_ticket': res.order, 'reverse_price': rev_price}
            logger.warning(f"Reversed {position.ticket} for {position.symbol} with {res.comment} At {position.profit}")
            return
        else:
            logger.error(f"Could not reverse {position.ticket} for {position.symbol} with {res.comment}")
    except Exception as exe:
        logger.error(f'An error occurred in function reverse_trade {exe}')
