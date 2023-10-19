import asyncio
from datetime import datetime, timezone
import pytz
from aiomql import Symbol, TimeFrame, Account



async def main():
    async with Account():
        now = datetime.now(pytz.timezone('Africa/Abidjan'))
        # now = now.replace(tzinfo=timezone.utc)
        print(now)
        sym = Symbol(name='EURUSD')
        await sym.init()
        bars = await sym.copy_rates_from(timeframe=TimeFrame.H1, date_from=now, count=24)
        rates = await sym.copy_rates_from_pos(timeframe=TimeFrame.H1, count=24)
        print(len(bars), len(rates))
        print(datetime.fromtimestamp(bars[-1].time), datetime.fromtimestamp(rates[-1].time))
        print(bars[-1].close, rates[-1].close)


asyncio.run(main())
