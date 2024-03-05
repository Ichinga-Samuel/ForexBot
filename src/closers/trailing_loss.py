from logging import getLogger

from aiomql import Positions, Symbol, OrderType, TradePosition, TimeFrame, Config, Order, TradeAction

logger = getLogger(__name__)


async def trail_sl(*, position: TradePosition):
    try:
        positions = Positions()
        config = Config()
        order = config.state.setdefault('profits', {}).setdefault(position.ticket, {})
        trail = order.get('sl_trail', 0.075)
        last_profit = order.get('last_profit', 0)
        profit = order.get('expected_profit', 0)
        if not profit:
            profit = await position.mt5.order_calc_profit(position.type, position.symbol, position.volume,
                                                          position.price_open, position.tp)
            config.state['profits'][position.ticket]['expected_profit'] = profit

        if position.profit < 0 and position.profit < (-profit * (1 - trail)) and position.profit < last_profit:
            sym = Symbol(name=position.symbol)
            await sym.init()
            rev = await check_reversal(sym=sym, position=position)
            if rev:
                res = await positions.close_by(position)
                if res.retcode == 10009:
                    logger.warning(f"Closed trade {position.ticket} with trail_sl")
                else:
                    logger.error(f"Unable to close trade in trail_sl {res.comment}")
            else:
                points = order.get('points', 0)
                if not points:
                    points = abs(position.price_open - position.sl) / sym.point
                    config.state['profits'][position.ticket]['points'] = points
                    # don't reset points
                positions = await positions.positions_get(ticket=position.ticket)
                position = positions[0]
                # check profit again
                mod = await modify_sl(position=position, sym=sym, trail=trail, points=points)
                if mod:
                    config.state['profits'][position.ticket]['last_profit'] = position.profit
    except Exception as exe:
        logger.error(f'An error occurred in function trail_sl {exe}')


async def check_reversal(*, sym: Symbol, position: TradePosition) -> bool:
    try:
        candles = await sym.copy_rates_from_pos(count=1000, timeframe=TimeFrame.M30)
        fast, slow = 8, 13
        candles.ta.ema(length=fast, append=True)
        candles.ta.ema(length=slow, append=True)
        candles.rename(**{f"EMA_{fast}": "fast", f"EMA_{slow}": "slow"})
        if position.type == OrderType.BUY:
            fxs = candles.ta_lib.cross(candles.fast, candles.slow, above=False)
            if fxs.iloc[-1]:
                return True
            else:
                return False
        elif position.type == OrderType.SELL:
            fxs = candles.ta_lib.cross(candles.fast, candles.slow, above=True)
            if fxs.iloc[-1]:
                return True
            else:
                return False
    except Exception as exe:
        logger.error(f'An error occurred in function check_reversal {exe}')
        return False


async def modify_sl(*, position: TradePosition, sym: Symbol, trail: float = 0.075, points):
    try:
        trail_points = trail * points
        points = max(trail_points, sym.trade_stops_level + sym.spread)
        dp = round(points * sym.point, sym.digits)
        tick = await sym.info_tick()
        price = tick.ask if position.type == OrderType.BUY else tick.bid
        sl = price - dp if position.type == OrderType.BUY else price + dp
        order = Order(position=position.ticket, sl=sl, tp=position.tp, action=TradeAction.SLTP)
        res = await order.send()
        if res.retcode == 10009:
            logger.warning(f"Successfully modified sl at {dp} for {position.symbol}")
            return True
        else:
            logger.error(f"Could not modify order sl {res.comment}")
            return False
    except Exception as exe:
        logger.error(f'An error occurred in function modify_sl {exe}')
        return False
