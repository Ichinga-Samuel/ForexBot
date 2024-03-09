from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame, Config, Order, TradeAction

logger = getLogger(__name__)


async def trail_sl(*, position: TradePosition):
    try:
        positions = Positions()
        config = Config()
        order = config.state.setdefault('loss', {}).setdefault(position.ticket, {})
        trail = getattr(config, 'sl_trail', order.get('sl_trail', 0.15))
        trail_start = getattr(config, 'sl_trail_start', order.get('sl_trail_start', 0.15))
        last_price = order.get('last_price', position.price_open)
        sym = Symbol(name=position.symbol)
        await sym.init()
        points = abs(position.price_open - position.sl) / sym.point
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        rem_points = abs(price - position.sl) / sym.point
        ratio = round(rem_points / points, 2)
        start = price < last_price if position.type == OrderType.BUY else price > last_price
        if position.profit < 0 and ratio <= trail_start and start:
            rev = await check_reversal(sym=sym, position=position)
            if rev:
                res = await positions.close_by(position)
                if res.retcode == 10009:
                    logger.warning(f"Closed trade {position.ticket} due to reversal")
                else:
                    logger.error(f"Unable to close trade in trail_sl {res.comment}")
            else:
                positions = await positions.positions_get(ticket=position.ticket)
                position = positions[0]
                enter = position.price_current < last_price if position.type == OrderType.BUY else (
                        position.price_current > last_price)
                if enter:
                    mod = await modify_sl(position=position, sym=sym, trail=trail, points=points)
                    if mod:
                        config.state['loss'][position.ticket]['last_price'] = position.sl
                        logger.warning(f"Modified sl for {position.ticket} with trail_sl")
    except Exception as exe:
        logger.error(f'An error occurred in function trail_sl {exe}')


async def check_reversal(*, sym: Symbol, position: TradePosition) -> bool:
    try:
        candles = await sym.copy_rates_from_pos(count=1000, timeframe=TimeFrame.H1)
        fast, slow = 8, 13
        candles.ta.ema(length=fast, append=True)
        candles.ta.ema(length=slow, append=True)
        candles.rename(**{f"EMA_{fast}": "fast", f"EMA_{slow}": "slow"})
        if position.type == OrderType.BUY:
            fbs = candles.ta_lib.below(candles.fast, candles.slow)
            cbf = candles.ta_lib.below(candles.close, candles.fast)
            if fbs.iloc[-1] and cbf.iloc[-1]:
                return True
            else:
                return False
        elif position.type == OrderType.SELL:
            fab = candles.ta_lib.above(candles.fast, candles.slow)
            caf = candles.ta_lib.above(candles.close, candles.fast)
            if fab.iloc[-1] and caf.iloc[-1]:
                return True
            else:
                return False
    except Exception as exe:
        logger.error(f'An error occurred in function check_reversal {exe}')
        return False


async def modify_sl(*, position: TradePosition, sym: Symbol, trail: float, points: float, extra=0.0, tries=4) -> bool:
    try:
        trail_points = trail * points
        points = max(trail_points, sym.trade_stops_level + sym.spread * (1 + extra))
        dp = round(points * sym.point, sym.digits)
        sl = position.sl - dp if position.type == OrderType.BUY else position.tp + dp
        order = Order(position=position.ticket, sl=sl, tp=position.tp, action=TradeAction.SLTP)
        res = await order.send()
        if res.retcode == 10009:
            logger.warning(f"Successfully modified sl at {dp} for {position.symbol}")
            return True
        elif res.retcode == 10016 and tries > 0:
            await modify_sl(position=position, sym=sym, trail=trail, points=points, extra=extra + 0.05, tries=tries - 1)
        else:
            logger.error(f"Could not modify order sl {res.comment}")
            return False
    except Exception as exe:
        logger.error(f'An error occurred in function modify_sl {exe}')
        return False
