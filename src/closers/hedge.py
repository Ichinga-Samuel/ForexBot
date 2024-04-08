from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, Config, OrderSendResult, OrderError
# from ..utils.sym_utils import calc_profit

logger = getLogger(__name__)


async def hedge_position(*, position: TradePosition):
    try:
        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        config = Config()
        order = config.state.setdefault('losing', {}).setdefault(position.ticket, {})
        winning = config.state.setdefault('winning', {})
        winning_order = winning.setdefault(position.ticket, {})
        hedges = config.state.setdefault('hedges', {})
        assert not position.comment.startswith('Rev'), f"Already hedged {position.ticket}:{position.comment}"
        hedge_point = order.get('hedge_point', -3)
        if position.profit <= hedge_point:
            sym = Symbol(name=position.symbol)
            await sym.init()
            res = await make_hedge(position=position, symbol=sym)
            hedges[position.ticket] = res.order
            winning[res.order] = winning_order
    except Exception as exe:
        logger.error(f'An error occurred in function hedge {exe}')


async def make_hedge(*, position: TradePosition, symbol: Symbol) -> OrderSendResult:
    osl = abs(position.sl - position.price_open)
    otp = abs(position.tp - position.price_open)
    if position.type == OrderType.BUY:
        sl = position.price_open + osl
        tp = position.price_open - otp
    else:
        sl = position.price_open - osl
        tp = round(position.price_open + otp, symbol.digits)
    order = Order(symbol=position.symbol, price=position.price_current, volume=position.volume,
                  type=position.type.opposite, sl=sl, tp=tp, comment=f"Rev{position.ticket}")
    res = await order.send()
    if res.retcode == 10009:
        logger.warning(f"Hedged {position.ticket} for {position.symbol} at {position.profit} with {res.order}")
        return res
    else:
        raise OrderError(f"Could not reverse {position.ticket} for {position.symbol} with {res.comment}")


async def check_hedge(*, main: int, rev: int):
    try:
        config = Config()
        hedges = config.state.setdefault('hedges', {})
        fixed_closer = config.state.setdefault('fixed_closer', {})
        pos = Positions()
        poss = await pos.positions_get()
        main_pos, rev_pos = None, None
        for p in poss:
            if p.ticket == main:
                main_pos = p
            elif p.ticket == rev:
                rev_pos = p
        if not main_pos and not rev_pos:
            hedges.pop(main) if main in hedges else ...
            return
        if main_pos:
            order = config.state.setdefault('losing', {}).setdefault(main_pos.ticket, {})
            hedge_point = order.get('hedge_point', -3)
            if main_pos.profit > 0:
                if rev_pos:
                    await pos.close_by(rev_pos)
                    order = fixed_closer.setdefault(main, {})
                    order['close'] = True

            if rev_pos and rev_pos.profit < hedge_point:
                await pos.close_by(rev_pos)
                if main_pos.profit < 0:
                    await pos.close_by(main_pos)
                    hedges.pop(main) if main in hedges else ...

        if not main_pos:
            if rev_pos:
                if rev_pos.profit > 0:
                    order = fixed_closer.setdefault(rev, {})
                    order['close'] = True
                    order['cut_off'] = 0.01
                if rev_pos.profit < 0:
                    await pos.close_by(rev_pos)
            hedges.pop(main) if main in hedges else ...
    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge {exe}')
