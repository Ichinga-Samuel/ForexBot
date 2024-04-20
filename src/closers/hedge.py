from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, Config, OrderSendResult, OrderError

# from ..utils.sym_utils import calc_profit, calc_loss

logger = getLogger(__name__)


async def hedge_position(*, position: TradePosition):
    try:
        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        config = Config()
        order = config.state.setdefault('losing', {}).setdefault(position.ticket, {})
        closer = config.state.setdefault('fixed_closer', {})
        winning = config.state.setdefault('winning', {})
        main_order = winning.setdefault(position.ticket, {})
        hedges = config.state.setdefault('hedges', {})
        assert not position.comment.startswith('Rev')
        hedge_point = order.get('hedge_point', -3.5)
        if position.profit <= hedge_point:
            sym = Symbol(name=position.symbol)
            await sym.init()
            res = await make_hedge(position=position, symbol=sym)
            hedges[position.ticket] = res.order
            order['hedge_point'] = position.profit
            closer[res.order] = {'close': False, 'cut_off': position.profit - 0.2}
            winning[res.order] = main_order | {'start_trailing': False, 'last_profit': 0}
    except AssertionError as _:
        pass
    except Exception as exe:
        logger.error(f'An error occurred in function hedge {exe}')


async def make_hedge(*, position: TradePosition, symbol: Symbol) -> OrderSendResult:
    osl = abs(position.sl - position.price_open)
    otp = abs(position.tp - position.price_open)
    diff = abs(position.price_open - position.price_current)
    if position.type == OrderType.BUY:
        sl = position.price_open + osl + diff
        tp = position.price_open - otp - diff
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
        winning = config.state.setdefault('winning', {})
        main_order = winning.setdefault(main, {})
        pos = Positions()
        poss = await pos.positions_get()
        main_pos, rev_pos = None, None
        for p in poss:
            if p.ticket == main:
                main_pos = p
            elif p.ticket == rev:
                rev_pos = p
        if main_pos is None and rev_pos is None:
            hedges.pop(main) if main in hedges else ...
            return

        if main_pos is not None:
            order_ = config.state.setdefault('losing', {}).setdefault(main, {})
            hedge_cutoff = order_.get('hedge_cutoff', 0)
            hedge_point = order_.get('hedge_point', -3.5)
            cut_off = order_.get('cut_off', -1)

            if main_pos.profit >= hedge_cutoff:
                if rev_pos is not None:
                    await pos.close_by(rev_pos)
                    logger.warning(f"Closed {rev_pos.symbol}:{rev_pos.comment} for {main_pos.ticket} at"
                                   f"{rev_pos.profit=}:{main_pos.profit=}")

                    close_order = fixed_closer.setdefault(main, {})
                    close_order['close'] = True
                    close_order['cut_off'] = cut_off
                    main_order['trail_start'] = abs(getattr(rev_pos, 'profit', hedge_point)) + 2
                    main_order['trail'] = 2
                    hedges.pop(main) if main in hedges else ...

        if main_pos is None:
            if rev_pos is not None:
                if rev_pos.profit > 0:
                    rev_order = winning.setdefault(rev, main_order)
                    rev_order['start_trailing'] = False
                    rev_order['trailing'] = False
                    rev_order['last_profit'] = 0
                    rev_order['trail_start'] = main_order.get('hedge_trail_start', 9)
                    rev_order['trail'] = main_order.get('hedge_trail', 2)
                    close_rev = fixed_closer.setdefault(rev, {})
                    logger.warning(f"Before {rev_pos.symbol}:{rev_pos.comment} {close_rev}")
                    close_rev['close'] = True
                    close_rev['cut_off'] = max(rev_pos.profit - 1, 0.5)
                    logger.warning(
                        f"{rev_pos.symbol}:{rev_pos.comment} for {rev_pos.profit}- cutoff={close_rev['cut_off']}")
                    close_rev = fixed_closer.setdefault(rev, {})
                    logger.warning(f"After {rev_pos.symbol}:{rev_pos.comment} {close_rev}")
                    # hedges.pop(main) if main in hedges else ...
                elif rev_pos.profit <= 0:
                    await pos.close_by(rev_pos)
                    logger.warning(f"Closed {rev_pos.comment}:{rev_pos.symbol} for {main} at {rev_pos.profit}:")
                    # hedges.pop(main) if main in hedges else ...
            hedges.pop(main) if main in hedges else ...
    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge {exe}')
