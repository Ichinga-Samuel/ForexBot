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

    def __init__(self, *, symbol, hedge_order=False, track_profit=False,
                 profit_checker=fixed_check_profit, use_exit_signal=False, **kwargs):
        hedger_params = {"hedge_point": 0.58} | kwargs.pop('hedger_params', {})
        cp = {'use_check_points': True, "check_points": {4: 1, 10: 10, -10: -10}, "close": True, "check_point": -10}
        check_profit_params = cp | kwargs.pop('check_profit_params', {})
        ram = RAM(risk_to_reward=1, fixed_amount=10)
        ram = kwargs.pop('ram', ram)
        super().__init__(symbol=symbol, hedge_order=hedge_order, ram=ram, track_profit=track_profit,
                         check_profit_params=check_profit_params, profit_checker=profit_checker,
                         hedger_params=hedger_params, use_exit_signal=use_exit_signal, **kwargs)

    async def create_order(self, *, order_type: OrderType, sl: float, tp: float):
        try:
            await self.symbol.info()
            tick = await self.symbol.info_tick()
            price = tick.ask if order_type == OrderType.BUY else tick.bid
            amount = await self.ram.get_amount()
            volume, sl = await self.symbol.compute_volume_sl(price=price, amount=amount, sl=sl, round_down=True,
                                                             use_limits=False, adjust=False)
            self.order.set_attributes(volume=volume, type=order_type, price=price, sl=sl, tp=tp,
                                      comment=self.parameters.get('name', self.__class__.__name__))
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.create_order")

    async def place_trade(self, *, order_type: OrderType, sl: float, tp: float, parameters: dict = None):
        try:
            self.parameters |= parameters or {}

            if await self.check_ram() is False:
                logger.warning(f'Could not place trade due to RAM for {self.symbol}')
                return

            await self.create_order(order_type=order_type, sl=sl, tp=tp)
            if await self.check_order() is False:
                return
            await self.send_order()
        except RuntimeError as _:
            pass
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.place_trade for {self.symbol}")
