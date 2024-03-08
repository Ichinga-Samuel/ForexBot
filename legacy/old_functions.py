async def check_hedge(*, main: int, rev: int):
    try:
        config = Config()
        hedges = config.state.get('hedges', {})
        pos = Positions()
        poss = await pos.positions_get(ticket=main)
        main_pos = poss[0] if poss else None
        poss = await pos.positions_get(ticket=rev)
        rev_pos = poss[0] if poss else None
        if main_pos and rev_pos:
            if main_pos.profit > 0:
                await pos.close_by(rev_pos)
                hedges.pop(main) if main in hedges else ...
            elif rev_pos.profit > 0:
                await extend_tp(position=rev_pos)
        if not main_pos and rev_pos:
            hedges.pop(main) if main in hedges else ...
    except Exception as exe:
        logger.error(f'An error occurred in function check_hedge {exe} of hedging')
