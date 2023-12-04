# aiomql
![GitHub](https://img.shields.io/github/license/ichinga-samuel/aiomql?style=plastic)
![GitHub issues](https://img.shields.io/github/issues/ichinga-samuel/aiomql?style=plastic)
![PyPI](https://img.shields.io/pypi/v/aiomql)

## Installation
```bash
pip install aiomql
```

## Key Features
- Asynchronous Python Library For MetaTrader 5
- Build bots for trading in different financial markets using a bot factory
- Use threadpool executors to run multiple strategies on multiple instruments concurrently
- Record and keep track of trades and strategies in csv files.
- Utility classes for using the MetaTrader 5 Library
- Sample Pre-Built strategies
- Trade sessions for managing trading sessions

## Simple Usage as an asynchronous MetaTrader5 Libray
```python
import asyncio
# import the class
from aiomql import MetaTrader, Account, TimeFrame, OrderType
async def main():
    mt5 = MetaTrader()
    await mt5.initialize()
    await mt5.login(123456, '*******', 'Broker-Server')
    symbols = await mt5.symbols_get()
    print(symbols)
    
asyncio.run(main())
```
## As a Bot Building FrameWork using a Sample Strategy
```python
from datetime import time
import logging

from aiomql.lib import FingerTrap
from aiomql import Bot, Account, ForexSymbol, Session, Sessions, RAM

logging.basicConfig(level=logging.INFO)


def build_bot():
    # Either initialize an account here with your login details here or set them in the aiomql.json file.
    # acc = Account(login=1234567, password='*******', server='Broker-Server')
    bot = Bot()

    # Prebuilt strategy from the library.
    # Disclaimer: These strategy is only for demonstration purposes.
    # The author of this library is not responsible for any losses incurred from using this strategy.

    # using trade sessions is optional. the strategy will run with a default session of 24 hours if not specified.
    # session start and end times are in UTC. Make sure to convert to UTC if you are in a different timezone.
    # sessions can be used to close positions at the end of a trading session.
    sess = Session(name='London', start=8, end=time(hour=15, minute=30), on_end='close_all')
    sess2 = Session(name='New York', start=13, end=time(hour=20, minute=30))
    sess3 = Session(name='Tokyo', start=23, end=time(hour=6, minute=30))
    sessions = Sessions(sess, sess2, sess3)
    
    # configurable parameters for the strategy
    params = {'trend_candles_count': 500, 'fast_period': 8}
    
    st1 = FingerTrap(symbol=ForexSymbol(name='GBPUSD'), params=params, sessions=sessions)
    st3 = FingerTrap(symbol=ForexSymbol(name='AUDUSD'), params=params, sessions=sessions)
    st4 = FingerTrap(symbol=ForexSymbol(name='USDCAD'), params=params, sessions=sessions)
    st5 = FingerTrap(symbol=ForexSymbol(name='USDJPY'), params=params, sessions=sessions)
    st6 = FingerTrap(symbol=ForexSymbol(name='EURGBP'), params=params, sessions=sessions)
    
    # Risk Management
    ram = RAM(risk=0.05, risk_to_reward=2)
    # change the risk management of a strategy. This is done on the trader attribute of the strategy.
    st5.trader.ram = ram 
    
    # add strategies to the bot
    bot.add_strategies([st1, st3, st4, st5, st6])
    bot.execute()


build_bot()
```
## API Documentation
see [API Documentation](https://github.com/Ichinga-Samuel/aiomql/tree/master/docs) for more details
