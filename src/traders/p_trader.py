from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class PTrader(BaseTrader):
    """Points Based Trader"""
    async def create_order(self, order_type: OrderType, sl: float = None):
        amount = await self.ram.get_amount()
        points = self.get_points(amount=amount)
        self.data |= self.parameters
        await self.create_order_points(order_type=order_type, points=points, amount=amount, use_limits=False)

    def get_points(self, *, amount):
        # points = self.symbol.compute_points(amount=amount, volume=self.symbol.volume_min)
        points = 100
        min_points = self.symbol.trade_stops_level + (self.symbol.spread * 1.5)
        return points if points >= min_points else min_points

    async def place_trade(self, *, order_type: OrderType, sl: float = None, parameters: dict = None):
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, sl=sl)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")
