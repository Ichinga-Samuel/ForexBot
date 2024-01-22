from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class PTrader(BaseTrader):
    """Points Based Trader"""
    async def create_order(self, order_type: OrderType):

        amount = await self.ram.get_amount()
        points = self.symbol.trade_stops_level * 2
        await self.create_order_points(order_type=order_type, points=points, amount=amount, use_limits=True)

    async def place_trade(self, order_type: OrderType, parameters: dict = None):
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")