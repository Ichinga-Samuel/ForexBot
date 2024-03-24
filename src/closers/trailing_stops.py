import asyncio

from logging import getLogger

from aiomql import Order, TradeAction, OrderType, TradePosition, Symbol, Positions, TimeFrame, Config, OrderSendResult

from ..utils.sleep import sleep
from ..utils.sym_utils import calc_profit

logger = getLogger(__name__)


async def check_stops(*, position: TradePosition):
    try:
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        trailing = order.get('trailing', False)
        last_profit = order.setdefault('last_profit', position.profit)
        trail = getattr(config, 'trail', order.get('trail', 0.15))
        trail_start = getattr(config, 'trail_start', order.get('trail_start', 0.50))
        extend_start = getattr(config, 'extend_start', order.get('extend_start', 0.95))
        target_profit = order.setdefault('target_profit',
                                         await position.mt5.order_calc_profit(position.type, position.symbol,
                                                                              position.volume,
                                                                              position.price_open, position.tp))

        if position.profit > (target_profit * trail_start) and position.profit >= last_profit:
            symbol = Symbol(name=position.symbol)
            await symbol.init()
            await modify_stops(position=position, trail=trail, sym=symbol, last_profit=last_profit,
                               trail_start=trail_start, extend_start=extend_start, trailing=trailing)

    except Exception as err:
        logger.error(f"{err} in modify_stop for {position.symbol}:{position.ticket}")


async def modify_stops(*, position: TradePosition, sym: Symbol, extra=0.01, tries: int = 4, trail: float = 0.15,
                       last_profit: float = 0.0, trail_start: float = 0.50, extend_start: float = 0.95, trailing=False):
    try:
        config = Config()
        positions = await Positions().positions_get(ticket=position.ticket)
        position = positions[0]
        assert position.profit > last_profit
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        points = int(abs(position.price_open - position.tp) / sym.point)
        captured_points = int(abs(position.tp - price) / sym.point)
        trail_points = int(trail * points)
        min_points = int(sym.trade_stops_level + sym.spread * (1 + extra))
        t_points = max(trail_points, min_points)
        dp = round(t_points * sym.point, sym.digits)
        dt = round(t_points * 0.55 * sym.point, sym.digits)
        flag = False
        change_tp = False
        if position.type == OrderType.BUY:
            sl = price - dp
            captured_profit = calc_profit(sym=sym, open_price=price, close_price=sl, volume=position.volume,
                                          order_type=OrderType.SELL)
            captured_profit = round(captured_profit, sym.digits)
            target_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                        volume=position.volume, order_type=OrderType.BUY)
            logger.warning(f"Trailing Stops for {position.symbol}:{position.ticket} is"
                           f" {captured_profit=} {target_profit=}")
            if captured_profit >= (extend_start * target_profit):
                tp = position.tp + dt
                change_tp = True
            else:
                tp = position.tp
            if trailing or (captured_profit > (trail_start * target_profit)):
                flag = True
        else:
            sl = price + dp
            captured_profit = calc_profit(sym=sym, open_price=price, close_price=sl, volume=position.volume,
                                          order_type=OrderType.BUY)
            captured_profit = round(captured_profit, sym.digits)
            target_profit = calc_profit(sym=sym, open_price=position.price_open, close_price=position.tp,
                                        volume=position.volume, order_type=OrderType.SELL)
            logger.warning(f"Trailing Stops for {position.symbol}:{position.ticket} is"
                           f" {captured_profit=} {target_profit=}")
            if captured_profit >= (extend_start * target_profit):
                tp = position.tp - dt
                change_tp = True
            else:
                tp = position.tp
            if trailing or captured_profit >= (trail_start * target_profit):
                flag = True
        if flag:
            res = await send_order(position=position, sl=sl, tp=tp)
            if res.retcode == 10009:
                config.state['profits'][position.ticket]['last_profit'] = position.profit
                if change_tp:
                    config.state['profits'][position.ticket]['target_profit'] = target_profit
                    config.state['profits'][position.ticket]['trailing'] = True
            elif res.retcode == 10016 and tries > 0:
                await modify_stops(position=position, trail=trail, sym=sym, extra=extra + 0.01,
                                   tries=tries - 1, last_profit=last_profit, trailing=trailing)
            else:
                logger.error(f"Trailing profits failed due to {res.comment} for {position.symbol}:{position.ticket}")
    except Exception as err:
        logger.error(f"Trailing profits failed due to {err} for {position.symbol}:{position.ticket}")


async def send_order(position: TradePosition, sl: float, tp: float) -> OrderSendResult:
    order = Order(position=position.ticket, sl=sl, tp=tp, action=TradeAction.SLTP)
    res = await order.send()
    return res


# change the interval to two minutes
async def trailing_stops(*, tf: TimeFrame = TimeFrame.M1):
    print('Trailing stops started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            tts = [check_stops(position=position) for position in positions if position.profit > 0]
            await asyncio.gather(*tts, return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function trailing_stops {exe}')
            await sleep(tf.time)
