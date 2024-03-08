from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class SPTrader(BaseTrader):
    async def create_order(self, *, order_type: OrderType, sl: float):
        amount = await self.ram.get_amount()
        await self.symbol.info()
        tick = await self.symbol.info_tick()
        points = (tick.ask - sl) / self.symbol.point if order_type == OrderType.BUY else (abs(tick.bid - sl) /
                                                                                          self.symbol.point)
        min_points = self.symbol.trade_stops_level + self.symbol.spread * 2
        points = max(min_points, points)
        await self.create_order_points(order_type=order_type, points=points, amount=amount, use_limits=True,
                                       round_down=False, adjust=True)
        self.data |= self.parameters

    async def place_trade(self, *, order_type: OrderType, sl,  parameters: dict = None):
        try:
            if self.use_ram:
                await self.check_ram()
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, sl=sl)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")
