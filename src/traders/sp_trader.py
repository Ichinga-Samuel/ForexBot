from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class SPTrader(BaseTrader):
    async def create_order(self, *, order_type: OrderType, sl: float = 0.0):
        amount = await self.ram.get_amount()
        await self.symbol.info()
        tick = await self.symbol.info_tick()
        min_points = self.symbol.trade_stops_level + (self.symbol.spread * 1.5)
        if sl:
            points = (tick.ask - sl) / self.symbol.point if order_type == OrderType.BUY else (tick.bid + sl) / self.symbol.point
        else:
            points = min_points
        points = max(points, min_points)
        await self.create_order_points(order_type=order_type, points=points, amount=amount, round_down=False)

    async def place_trade(self, *, order_type: OrderType, parameters: dict = None, sl: float = 0.0):
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, sl=sl)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")