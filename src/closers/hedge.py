from logging import getLogger

from aiomql import Order, OrderType, TradePosition, Symbol, Positions, Config, OrderSendResult, OrderError

logger = getLogger(__name__)


async def hedge_position(*, position: TradePosition):
    try:
        position = await Positions().positions_get(ticket=position.ticket)
        position = position[0]
        config = Config()
        order = config.state['losing'][position.ticket]
        winning = config.state['winning']
        fixed_closer = config.state['fixed_closer']
        main_order = winning[position.ticket]
        hedges = config.state['hedges']
        assert not position.comment.startswith('Rev')
        hedge_point = order['hedge_point']
        if position.profit <= hedge_point:
            sym = Symbol(name=position.symbol)
            await sym.init()
            res = await make_hedge(position=position, symbol=sym)
            hedges[position.ticket] = res.order
            order['hedge_point'] = position.profit
            fixed_closer[res.order] = {'close': False, 'cut_off': -1}
            winning[res.order] = {**main_order} | {'start_trailing': False, 'last_profit': 0}
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
        logger.info(f"Hedged {position.ticket} for {position.symbol} at {position.profit} with {res.order}")
        return res
    else:
        raise OrderError(f"Could not reverse {position.ticket} for {position.symbol} with {res.comment}")


async def check_hedge(*, main: int, rev: int):
    try:
        config = Config()
        hedges = config.state['hedges']
        fixed_closer = config.state['fixed_closer']
        winning = config.state['winning']
        main_order = winning[main]
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
            order_ = config.state['losing'][main]
            hedge_cutoff = order_['hedge_cutoff']
            cut_off = order_['cut_off']

            if main_pos.profit >= hedge_cutoff:
                if rev_pos is not None:
                    await pos.close_by(rev_pos)
                    logger.warning(f"Closed {rev_pos.symbol}:{rev_pos.comment} for {main_pos.ticket} at"
                                   f"{rev_pos.profit=}:{main_pos.profit=}")

                    close_order = fixed_closer.setdefault(main, {})
                    close_order['close'] = True
                    close_order['cut_off'] = cut_off
                    hedges.pop(main) if main in hedges else ...

        if main_pos is None:
            if rev_pos is not None:
                if rev_pos.profit > 0:
                    adjust = main_order['adjust']
                    rev_order = winning[rev]
                    rev_order['start_trailing'] = True
                    close_rev = fixed_closer[rev]
                    close_rev['close'] = True
                    close_rev['cut_off'] = max(rev_pos.profit - adjust, adjust)
                elif rev_pos.profit <= 0:
                    await pos.close_by(rev_pos)
                    logger.info(f"Closed {rev_pos.comment}:{rev_pos.symbol} at {rev_pos.profit}")
            hedges.pop(main) if main in hedges else ...
    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge {exe}')
