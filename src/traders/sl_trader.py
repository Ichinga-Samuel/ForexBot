from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class SLTrader(BaseTrader):
    async def create_order(self, order_type: OrderType, sl):
        amount = await self.ram.get_amount()
        await self.create_order_sl(order_type=order_type, sl=sl, amount=amount, use_limits=False)

    async def place_trade(self, *, order_type: OrderType, sl: float, parameters: dict = None):
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, sl=sl)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")