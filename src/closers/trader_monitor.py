import asyncio
from logging import getLogger

from aiomql import Positions, TimeFrame, Config

from ..utils.sleep import sleep
from .fixed_closer import fixed_closer
from .trailing_stops import check_stops
from .trailing_loss import trail_sl
from .closer import OpenTrade

logger = getLogger(__name__)


async def monitor(*, tf: TimeFrame = TimeFrame.M1, key: str = 'trades'):
    print('Trade Monitoring started')
    pos = Positions()
    while True:
        try:
            positions = await pos.positions_get()
            config = Config()
            tasks = []

            # use trailing stops
            tts = getattr(config, 'trailing_stops', False)
            if tts:
                print('Using trailing stops')
                tts = [check_stops(position=position) for position in positions if position.profit > 0]
                tasks.extend(tts)

            # use exit signals
            es = getattr(config, 'exit_signals', False)
            if es:
                print('Using exit signals')
                data = config.state.get(key, {})
                open_trades = [OpenTrade(position=p, parameters=data[p.ticket]) for p in positions if p.ticket in data]
                closers = [trade.close() for trade in open_trades]
                tasks.extend(closers)

            # use trailing stop loss
            tsl = getattr(config, 'trailing_loss', False)
            if tsl:
                print('Using trailing stop loss')
                tsl = [trail_sl(position=position) for position in positions if position.profit < 0]
                tasks.extend(tsl)

            # use fixed_closer
            uc = getattr(config, 'fixed_closer', False)
            if uc:
                print('Using fixed closer')
                fc = [fixed_closer(position=position) for position in positions if position.profit < 0]
                tasks.extend(fc)

            await asyncio.gather(*tasks, return_exceptions=True)
            await sleep(tf.time)
        except Exception as exe:
            logger.error(f'An error occurred in function monitor {exe}')
            await sleep(tf.time)
