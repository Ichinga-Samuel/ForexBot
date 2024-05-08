from logging import getLogger

from aiomql import OrderType, OrderSendResult

from .base_trader import BaseTrader

logger = getLogger(__name__)


class BTrader(BaseTrader):
    async def create_order(self, *, order_type: OrderType, sl: float = 0):
        try:
            await self.symbol.info()
            tick = await self.symbol.info_tick()
            self.ram.max_amount = 12
            self.ram.min_amount = 12

            amount = await self.ram.get_amount()
            points = self.symbol.compute_points(amount=amount, volume=self.symbol.volume_min)
            comment = self.parameters.get('name', self.__class__.__name__)
            self.order.set_attributes(volume=self.symbol.volume_min, type=order_type, comment=comment)
            if self.multiple:
                self.set_multiple_stop_levels(points=points, tick=tick)
            else:
                self.set_trade_stop_levels(points=points, tick=tick)
            self.data |= self.parameters
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.create_order")

    def save_profit(self, result: OrderSendResult, profit):
        try:
            winning = ({'current_profit': profit, 'trail_start': 16, 'trail': 4, 'trailing': False,
                        'extend_start': 0.75, 'start_trailing': True, 'extend_by': 4, 'use_trails': True,
                        'trails': {12: 8, 4: 1, 7: 3, 5: 2}, 'rentry_trails': {2: 1, 3: 1.5, 4: 2.5, 5: 3.5},
                        'last_profit': 0, 'adjust': 3}
                       | self.winning)

            losing = {'trail_start': 0.75, 'sl_limit': 5, 'trail': 0.75, 'trailing': True,
                      'last_profit': 0, 'hedge_point': -7, 'cut_off': -1, 'mul_vol': 2, 'link_up': True,
                      'hedge_cutoff': 0} | self.losing
            fixed_closer = {'close': False, 'cut_off': -1} | self.fixed_closer
            self.config.state['winning'][result.order] = winning
            self.config.state['losing'][result.order] = losing
            self.config.state['fixed_closer'][result.order] = fixed_closer
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.save_profit")

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


# winning = ({'current_profit': profit, 'trail_start': 4.5, 'trail': 1.5, 'trailing': False,
#                         'extend_start': 0.75, 'start_trailing': True, 'extend_by': 0.5, 'use_trails': True,
#                         'trails': {4.5: 3.5, 5: 3.5, 6: 4.5, 7: 6.5, 8: 6.0, 10: 8, 9: 7}, 'last_profit': 0}
#                        | self.trail_profits)
