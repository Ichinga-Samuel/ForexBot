from logging import getLogger

from aiomql import OrderType, OrderSendResult

from .base_trader import BaseTrader

logger = getLogger(__name__)


class PointTrader(BaseTrader):
    async def create_order(self, *, order_type: OrderType, points: int):
        try:
            await self.symbol.info()
            self.ram.risk_to_reward = 1/3
            tick = await self.symbol.info_tick()
            amount = await self.ram.get_amount()
            comment = self.parameters.get('name', self.__class__.__name__)
            sl_points = points / self.ram.risk_to_reward
            sl_points = max(sl_points, self.symbol.trade_stops_level + self.symbol.spread)
            print(amount)
            volume, sl_points = await self.symbol.compute_volume_points(amount=amount, points=sl_points, use_limits=True,
                                                           adjust=False)
            print(self.symbol.trade_stops_level, sl_points, points, volume)
            tp = self.symbol.point * points
            sl = self.symbol.point * sl_points
            sl = tick.ask - sl if order_type == OrderType.BUY else tick.bid + sl
            tp = tick.ask + tp if order_type == OrderType.BUY else tick.bid - tp
            price = tick.ask if order_type == OrderType.BUY else tick.bid
            self.order.set_attributes(volume=volume, type=order_type, comment=comment, tp=tp, sl=sl, price=price)
            self.data |= self.parameters
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.create_order")

    def save_profit(self, result: OrderSendResult, profit):
        try:
            pass
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.save_profit")

    async def place_trade(self, *, order_type: OrderType, points: int, parameters: dict = None):
        try:
            if self.use_ram:
                await self.check_ram()
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, points=points)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err} in {self.order.symbol} {self.__class__.__name__}.place_trade")
