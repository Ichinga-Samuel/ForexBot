from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame, Config, Order, TradeAction

from ..utils import calc_loss

logger = getLogger(__name__)


async def trail_sl(*, position: TradePosition):
    try:
        positions = Positions()
        config = Config()
        order = config.state.setdefault('loss', {}).setdefault(position.ticket, {})
        trail_start = getattr(config, 'sl_trail_start', order.get('sl_trail_start', 0.8))
        last_profit = order.get('last_profit', 0)
        sym = Symbol(name=position.symbol)
        await sym.init()
        l_points = order.get('l_points', 0.0)
        points = abs(position.price_open - position.sl) / sym.point
        points = max(l_points, points)
        loss = calc_loss(sym=sym, open_price=position.price_open, close_price=position.sl, volume=position.volume,
                         order_type=position.type)
        trail_loss = trail_start * loss
        if position.profit < 0 and position.profit <= trail_loss and position.profit < last_profit:
            logger.error(f"Trade {position.ticket} is in loss {position.profit} with {trail_loss} trail_loss"
                         f" {last_profit} last_profit")
            rev = await check_reversal(sym=sym, position=position)
            if rev:
                res = await positions.close_by(position)
                if res.retcode == 10009:
                    logger.warning(f"Closed trade {position.ticket} due to reversal")
                else:
                    logger.error(f"Unable to close trade in trail_sl for {position.ticket}:{position.symbol}"
                                 f" due to {res.comment}")
            else:
                positions = await positions.positions_get(ticket=position.ticket)
                position = positions[0]
                mod = await modify_sl(position=position, sym=sym, trail=trail_start, points=points)
                if mod:
                    config.state['loss'][position.ticket]['last_profit'] = position.profit
                    logger.warning(f"Trailed stop loss {position.ticket}:{position.symbol}")
    except Exception as exe:
        logger.error(f'Trailing stop loss failed due to {exe} for {position.ticket}:{position.symbol}')


async def check_reversal(*, sym: Symbol, position: TradePosition) -> bool:
    try:
        candles = await sym.copy_rates_from_pos(count=1000, timeframe=TimeFrame.H1)
        fast, mid, slow = 13, 21, 34
        candles.ta.ema(length=fast, append=True)
        candles.ta.ema(length=slow, append=True)
        candles.ta.ema(length=mid, append=True)
        candles.rename(**{f"EMA_{fast}": "fast", f"EMA_{slow}": "slow", f"EMA_{mid}": "mide"})
        if position.type == OrderType.BUY:
            mbs = candles.ta_lib.below(candles.mide, candles.slow)
            fbs = candles.ta_lib.below(candles.fast, candles.mide)
            cbf = candles.ta_lib.below(candles.close, candles.fast)
            if fbs.iloc[-1] and cbf.iloc[-1] and mbs.iloc[-1]:
                return True
            else:
                return False
        elif position.type == OrderType.SELL:
            fab = candles.ta_lib.above(candles.fast, candles.mide)
            mas = candles.ta_lib.above(candles.mide, candles.slow)
            caf = candles.ta_lib.above(candles.close, candles.fast)
            if fab.iloc[-1] and caf.iloc[-1] and mas.iloc[-1]:
                return True
            else:
                return False
    except Exception as exe:
        logger.error(f'An error occurred in function check_reversal {exe} for {position.ticket}:{position.symbol}')
        return False


async def modify_sl(*, position: TradePosition, sym: Symbol, trail: float, points: float, extra=0.0, tries=4) -> bool:
    try:
        trail_points = trail * points
        points = max(trail_points, sym.trade_stops_level + sym.spread * (1 + extra))
        dp = round(points * sym.point, sym.digits)
        sl = position.price_current - dp if position.type == OrderType.BUY else position.price_current + dp
        order = Order(position=position.ticket, sl=sl, tp=position.tp, action=TradeAction.SLTP)
        res = await order.send()
        if res.retcode == 10009:
            logger.warning(f"Successfully modified sl at {dp} for {position.ticket}:{position.symbol}")
            return True
        elif res.retcode == 10016 and tries > 0:
            await modify_sl(position=position, sym=sym, trail=trail, points=points, extra=extra + 0.05, tries=tries - 1)
        else:
            logger.error(f"Trailing stop loss failed due to {res.comment} for {position.ticket}:{position.symbol}")
            return False
    except Exception as exe:
        logger.error(f'Trailing stop loss failed due to {exe} for {position.ticket}:{position.symbol}')
        return False
