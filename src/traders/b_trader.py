from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class BTrader(BaseTrader):
    async def create_order(self, *, order_type: OrderType, sl: float = 0):
        try:
            await self.symbol.info()
            tick = await self.symbol.info_tick()
            self.ram.max_amount = 6
            self.ram.min_amount = 6
            self.trail_profits = {'trail_start': 6, 'trail': 2, 'trailing': False, 'extend_start': 0.8,
                                  'start_trailing': True, 'extend_by': 2, 'take_profit': 9}
            self.trail_loss = {'hedge_point': -3.0}
            amount = await self.ram.get_amount()
            logger.warning(f"{amount=}")
            points = self.symbol.compute_points(amount=amount, volume=self.symbol.volume_min*4)
            comment = self.parameters.get('name', self.__class__.__name__)
            self.order.set_attributes(volume=(self.symbol.volume_min*4), type=order_type, comment=comment)
            if self.multiple:
                self.set_multiple_stop_levels(points=points, tick=tick)
            else:
                self.set_trade_stop_levels(points=points, tick=tick)
            self.data |= self.parameters
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.create_order")

    async def place_trade(self, *, order_type: OrderType, sl: float = 0, parameters: dict = None):
        try:
            if self.use_ram:
                await self.check_ram()

            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err} in {self.order.symbol} {self.__class__.__name__}.place_trade")
