from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class PTrader(BaseTrader):
    async def create_order(self, *, order_type: OrderType):
        try:
            await self.symbol.info()
            tick = await self.symbol.info_tick()
            amount = await self.ram.get_amount()
            points = self.symbol.compute_points(amount=amount, volume=self.symbol.volume_min)
            comment = self.parameters.get('name', self.__class__.__name__)
            self.order.set_attributes(volume=self.symbol.volume_min, type=order_type, comment=comment)
            self.set_trade_stop_levels(points=points, tick=tick)
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.create_order")

    async def place_trade(self, *, order_type: OrderType, parameters: dict = None):
        try:
            if self.use_ram:
                await self.check_ram()
            self.parameters |= parameters.copy() or {}
            await self.create_order(order_type=order_type)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err} in {self.order.symbol} {self.__class__.__name__}.place_trade")
