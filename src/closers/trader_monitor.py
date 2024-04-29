import asyncio
from logging import getLogger

from aiomql import Positions, Config

from ..utils.sleep import sleep
from .fixed_closer import fixed_closer
from .trailing_profit import trail_tp
from .trailing_loss import trail_sl
from .closer import OpenTrade
from .hedge import check_hedge, hedge_position

logger = getLogger(__name__)


async def monitor(*, tf: int = 31, key: str = 'trades'):
    print('Trade Monitoring started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            config = Config()
            hedged = config.state.get('hedges', {})
            main = list(hedged.keys())
            rev = list(hedged.values())
            hedged_orders = main + rev
            tasks = []

            # use hedging
            hedging = getattr(config, 'hedging', False)
            if hedging:
                hedge = [hedge_position(position=position) for position in positions if position.profit < 0 and
                         position.ticket not in hedged_orders]
                check_hedges = [check_hedge(main=main, rev=rev) for main, rev in hedged.items()]
                hedge_tasks = check_hedges + hedge
                await asyncio.gather(*hedge_tasks, return_exceptions=True)

            fixed = config.state.get('fixed_closer', {})
            fixed = [ticket for ticket, order in fixed.items() if order.get('close', False)]

            # use exit signals
            es = getattr(config, 'exit_signals', False)
            if es:
                data = config.state.get(key, {})
                open_trades = [OpenTrade(position=p, parameters=data[p.ticket]) for p in positions if p.ticket in data
                               and p.ticket not in hedged]
                closers = [trade.close() for trade in open_trades]
                tasks.extend(closers)

            # use trailing stop loss
            tsl = getattr(config, 'trailing_loss', False)
            if tsl:
                tsl = [trail_sl(position=position) for position in positions if position.profit < 0]
                tasks.extend(tsl)

            # use fixed_closer
            uc = getattr(config, 'fixed_closer', False)
            if uc:
                fc = [fixed_closer(position=position) for position in positions if position.ticket in fixed]
                tasks.extend(fc)

            # use trailing stops
            tts = getattr(config, 'trailing_stops', False)
            if tts:
                tts = [trail_tp(position=position) for position in positions if position.profit > 0]
                tasks.extend(tts)

            await asyncio.gather(*tasks, return_exceptions=True)
            await sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function monitor {exe}')
            await sleep(tf)
