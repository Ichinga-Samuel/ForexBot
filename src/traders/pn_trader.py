from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class PNTrader(BaseTrader):
    async def create_order(self, *, order_type: OrderType, sl: float, volume):
        await self.symbol.info()
        tick = await self.symbol.info_tick()
        points = (tick.ask - sl) / self.symbol.point if order_type == OrderType.BUY else (abs(tick.bid - sl) /
                                                                                          self.symbol.point)
        comment = self.parameters.get('name', self.__class__.__name__)
        self.order.set_attributes(volume=volume, type=order_type, comment=comment)
        if self.multiple:
            self.set_multiple_stop_levels(points=points, tick=tick)
        else:
            self.set_trade_stop_levels(points=points, tick=tick)
        self.data |= self.parameters

    async def place_trade(self, *, order_type: OrderType, sl: float, volume: float, parameters: dict = None):
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, sl=sl, volume=volume)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")
