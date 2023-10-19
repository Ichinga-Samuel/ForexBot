import asyncio
from datetime import datetime
from logging import getLogger

from aiomql import Trader, Positions, RAM, Symbol, OrderType, Result
from aiomql.trader import dict_to_string

logger = getLogger(__name__)


class MultiTrader(Trader):
    def __init__(self, symbol: Symbol, ram: RAM = None, multiplier=5):
        super().__init__(symbol=symbol, ram=ram)
        self.positions = Positions(symbol=symbol.name)
        self.ram = ram or RAM(risk_to_reward=2, amount=2.5)
        self.multiplier = multiplier

    async def create_order(self, order_type: OrderType, pips: float):
        res = await self.positions.positions_get()
        res.sort(key=lambda pos: pos.time_msc)
        if len(res) and res[-1].profit < 0:
            raise RuntimeError(f"Last trade in a losing position: {res[0].ticket}")
        volume = await self.ram.get_volume(symbol=self.symbol, pips=pips)
        self.order.volume = volume
        self.order.type = order_type
        await self.set_order_limits(pips=pips)

    async def place_trade(self, order_type: OrderType, params: dict = None, **kwargs):
        """Places a trade based on the order_type.

        Args:
            order_type (OrderType): Type of order
            params: parameters to be saved with the trade
            kwargs: keyword arguments as required for the specific trader
        """
        try:
            print(kwargs)
            await self.create_order(order_type=order_type, **kwargs)

            # Check the order before placing it
            check = await self.order.check()
            if check.retcode != 0:
                logger.warning(
                    f"Symbol: {self.order.symbol}\nResult:\n{dict_to_string(check.get_dict(include={'comment', 'retcode'}), multi=True)}")
                return

            # Send the orders.
            results = await asyncio.gather(*[self.order.send() for _ in range(self.multiplier)])
            result = results[0]
            if result.retcode != 10009:
                logger.warning(
                    f"Symbol: {self.order.symbol}\nResult:\n{dict_to_string(result.get_dict(include={'comment', 'retcode'}), multi=True)}")
                return

            logger.info(f"Symbol: {self.order.symbol}\nOrder: {dict_to_string(result.dict, multi=True)}\n")

            # save trade result and passed in parameters
            if result.retcode == 10009 and self.config.record_trades:
                params = params or {}
                params['expected_profit'] = check.profit
                params['date'] = (date := datetime.utcnow())
                params['time'] = date.timestamp()
                res = Result(result=result, parameters=params)
                await res.save_csv()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")
