from logging import getLogger

from aiomql import OrderType

from ..closers.trailing_profit import trail_tp
from ..closers.check_profits import fixed_check_profit
from ..utils.ram import RAM
from .base_trader import BaseTrader

logger = getLogger(__name__)


class PTrader(BaseTrader):
    volumes: dict = {'Volatility 10 Index': 1.5, 'Volatility 100 (1s) Index': 2.5, 'Volatility 25 Index': 2,
                     'Volatility 25 (1s) Index': 1, 'Volatility 75 Index': 2, 'Volatility 10 (1s) Index': 1.2,
                     'Volatility 75 (1s) Index': 1, 'Volatility 50 Index': 1, 'Volatility 50 (1s) Index': 1}

    def __init__(self, *, symbol, hedge_order=False, profit_tracker=trail_tp,
                 profit_checker=fixed_check_profit, use_exit_signal=False, **kwargs):
        hedger_params = {"hedge_point": 0.58} | kwargs.pop('hedger_params', {})
        cp = {'use_check_points': True, "check_points": {12: 8, 16: 13, 22: 18, 10: 7, 7: 4, 4: 1}}
        check_profit_params = cp | kwargs.pop('check_profit_params', {})
        ram = RAM(risk_to_reward=3, fixed_amount=3)
        ram = kwargs.pop('ram', ram)
        super().__init__(symbol=symbol, hedge_order=hedge_order, profit_tracker=profit_tracker, ram=ram,
                         check_profit_params=check_profit_params, profit_checker=profit_checker,
                         hedger_params=hedger_params, use_exit_signal=use_exit_signal, **kwargs)

    async def create_order(self, *, order_type: OrderType):
        try:
            await self.symbol.info()
            tick = await self.symbol.info_tick()
            amount = await self.ram.get_amount()
            volume_mul = self.volumes.get(self.symbol.name, 1)
            volume = volume_mul * self.symbol.volume_min
            points = self.symbol.compute_points(amount=amount, volume=volume)
            comment = self.parameters.get('name', self.__class__.__name__)
            self.order.set_attributes(volume=volume, type=order_type, comment=comment)
            self.set_trade_stop_levels(points=points, tick=tick)
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.create_order")

    async def place_trade(self, *, order_type: OrderType, parameters: dict = None):
        try:
            ok = await self.check_ram()
            if ok is False:
                logger.warning(f'Could not place trade due to RAM for {self.symbol}')
                return

            self.parameters |= parameters.copy() or {}
            await self.create_order(order_type=order_type)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err} in {self.order.symbol} {self.__class__.__name__}.place_trade")
