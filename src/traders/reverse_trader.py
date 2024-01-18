from logging import getLogger
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio

from aiomql import Trader, Positions, RAM, OrderType, ForexSymbol, Order, OrderSendResult, Result
from aiomql.utils import dict_to_string

from ..symbols import FXSymbol
from .ram import RAM

logger = getLogger(__name__)


class ReverseTrader(Trader):
    """Place the reverse of a trade"""
    order_format = "symbol: {symbol}\norder_type: {order_type}\npoints: {points}\namount: {amount}\n" \
                   "volume: {volume}\nrisk_to_reward: {risk_to_reward}\nstrategy: {strategy}\n" \
                   "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} " \
                   "seconds from now. No reply will be considered as 'cancel'\n" \
                   "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    def __init__(self, symbol: ForexSymbol | FXSymbol, ram=RAM(risk_to_reward=1.5, points=0)):
        super().__init__(symbol=symbol, ram=ram)
        self.positions = Positions(symbol=symbol.name)
        self.second_order = Order(symbol=symbol.name)

    async def create_order(self, order_type: OrderType):
        self.order.type = order_type
        self.second_order.deviation = 5
        self.second_order.type = order_type.opposite
        amount = self.ram.amount or await self.ram.get_amount()
        points = self.ram.points or self.symbol.trade_stops_level * 3
        volume = await self.symbol.compute_volume(points=points, amount=amount)
        points2 = (self.ram.points / 2) or self.symbol.trade_stops_level * 1.5
        volume2 = await self.symbol.compute_volume(points=points2, amount=amount/2)
        self.order.volume = volume
        self.order.comment = self.parameters.get('name', '')
        self.second_order.volume = volume2
        self.second_order.comment = f"Reversed {self.parameters.get('name', '')}"
        tick = await self.symbol.info_tick()
        first_order = self.get_trade_stop_levels(points=points, order_type=order_type, rr=self.ram.risk_to_reward, tick=tick)
        second_order = self.get_trade_stop_levels(points=points2, order_type=order_type.opposite, rr=1, tick=tick)
        self.order.set_attributes(**first_order)
        self.second_order.set_attributes(**second_order)

    def get_trade_stop_levels(self, *, points, order_type: OrderType, rr, tick) -> dict:
        points = points * self.symbol.point
        sl = tp = points
        if order_type == OrderType.BUY:
            sl = round(tick.ask - sl, self.symbol.digits)
            tp = round(tick.ask + tp * rr, self.symbol.digits)
            price = tick.ask
        else:
            sl = round(tick.bid + sl, self.symbol.digits)
            price = tick.bid
            tp = round(tick.bid - tp * rr, self.symbol.digits)
        return {'price': price, 'sl': sl, 'tp': tp}

    async def send_order(self):
        """Send the order to the broker."""
        result = self.order.send()
        result2 = self.second_order.send()
        result, result2 = await asyncio.gather(*[result, result2])

        if result.retcode != 10009:
            logger.warning(f"Symbol: {self.order.symbol}\nResult:\n"
                           f"{dict_to_string(result.get_dict(include={'comment', 'retcode'}), multi=True)}")
            return
        logger.info(f"Symbol: {self.order.symbol}\nOrder: {dict_to_string(result.dict, multi=True)}\n")
        parameters = self.parameters.copy()
        await self.record_trade(result, parameters, name=parameters['name'])

        if result2.retcode != 10009:
            logger.warning(f"Symbol: {self.order.symbol}\nResult:\n"
                           f"{dict_to_string(result2.get_dict(include={'comment', 'retcode'}), multi=True)}")
            return
        logger.info(f"Symbol: {self.order.symbol}\nOrder: {dict_to_string(result2.dict, multi=True)}\n")
        params = self.parameters.copy()
        params['name'] = f"Reversed {params['name']}"
        await self.record_trade(result2, params, name=parameters['name'])

    async def record_trade(self, result: OrderSendResult, parameters: dict, name: str = ''):
        """Record the trade in a csv file.

        Args:
            result (OrderSendResult): Result of the order send
            parameters: parameters of the trading strategy used to place the trade
            name: Name of the trading strategy
        """
        if result.retcode != 10009 or not self.config.record_trades:
            return
        params = parameters
        profit = await self.order.calc_profit()
        params["expected_profit"] = profit
        date = datetime.utcnow()
        date = date.replace(tzinfo=ZoneInfo("UTC"))
        params["date"] = str(date.date())
        params["time"] = str(date.time())
        res = Result(result=result, parameters=params, name=name)
        await res.save_csv()

    async def place_trade(self, order_type: OrderType, parameters: dict = None):
        """Places a trade based on the order_type.
        Args:
            order_type (OrderType): Type of order
            parameters: parameters of the trading strategy used to place the trade
        """
        try:
            self.parameters |= (parameters or {})
            await self.create_order(order_type=order_type)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")