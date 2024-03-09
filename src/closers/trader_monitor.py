import asyncio
from logging import getLogger

from aiomql import Positions, Config

from ..utils.sleep import sleep
from .fixed_closer import fixed_closer
from .trailing_stops import check_stops
from .trailing_loss import trail_sl
from .closer import OpenTrade
from .hedge import hedge, check_hedge, last_chance

logger = getLogger(__name__)


async def monitor(*, tf: int = 20, key: str = 'trades'):
    print('Trade Monitoring started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            config = Config()
            hedges = config.state.setdefault('hedges', {})
            logger.warning(f'{hedges=}')
            unhedged = config.state.get('last_chance', {})
            revs = [v['rev'] for v in hedges.values() if (isinstance(v, dict) and 'rev' in v)]
            lc = list(unhedged.keys())
            hedged = list(hedges.keys()) + lc
            tasks = []

            # use exit signals
            es = getattr(config, 'exit_signals', False)
            if es:
                data = config.state.get(key, {})
                open_trades = [OpenTrade(position=p, parameters=data[p.ticket]) for p in positions if p.ticket in data]
                closers = [trade.close() for trade in open_trades]
                tasks.extend(closers)

            # use trailing stop loss
            tsl = getattr(config, 'trailing_loss', False)
            if tsl:
                exclude = lc + revs
                tsl = [trail_sl(position=position) for position in positions if (position.profit < 0 and position.ticket
                       not in exclude)]
                tasks.extend(tsl)

            # use fixed_closer
            uc = getattr(config, 'fixed_closer', False)
            if uc:
                fc = [fixed_closer(position=position) for position in positions if position.profit < 0]
                tasks.extend(fc)

            # use trailing stops
            tts = getattr(config, 'trailing_stops', False)
            if tts:
                tts = [check_stops(position=position) for position in positions
                       if (position.profit > 0 and position.ticket not in revs)]
                tasks.extend(tts)

            # hedge
            hedging = getattr(config, 'hedging', False)
            if hedging:
                main = []
                exclude = hedged + lc
                hg = [hedge(position=position) for position in positions if position.profit < 0 and position.ticket
                      not in exclude]
                lcs = [last_chance(position=position) for position in positions if
                       (position.ticket in lc and position.profit < 0)]

                ch = [check_hedge(main=k, rev=k['rev']) for k in hedges]
                main.extend(hg)
                main.extend(ch)
                main.extend(lcs)
                await asyncio.gather(*main, return_exceptions=True)

            await asyncio.gather(*tasks, return_exceptions=True)
            await sleep(tf)
        except Exception as exe:
            logger.error(f'An error occurred in function monitor {exe}')
            await sleep(tf)
