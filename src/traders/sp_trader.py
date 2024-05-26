from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader
from ..utils.ram import RAM
from ..closers.atr_trailer import atr_trailer
from ..closers.check_profits import ratio_check_profit

logger = getLogger(__name__)


class SPTrader(BaseTrader):
    def __init__(self, *, symbol, hedge_order=False, profit_tracker=atr_trailer,
                 profit_checker=ratio_check_profit, **kwargs):
        cp = {'use_check_points': False,
              "check_points": {0.3: 0.1, 0.5: 0.3, 0.4: 0.2, 0.6: 0.4, 0.7: 0.5, 0.8: 0.6, 0.9: 0.7, 0.95: 0.8}}
        hedger_params = {"hedge_point": 0.75} | kwargs.pop('hedger_params', {})
        track_loss_params = {"trail_start": 0.75} | kwargs.pop('track_loss_params', {})
        check_profit_params = cp | kwargs.pop('check_profit_params', {})
        ram = RAM(min_amount=5, max_amount=100, risk_to_reward=2, risk=0.1)
        ram = kwargs.pop('ram', ram)
        super().__init__(symbol=symbol, hedge_order=hedge_order, profit_tracker=profit_tracker, ram=ram,
                         check_profit_params=check_profit_params, profit_checker=profit_checker,
                         track_loss_params=track_loss_params, hedger_params=hedger_params, **kwargs)

    async def create_order(self, *, order_type: OrderType, sl: float, tp: float):
        amount = await self.ram.get_amount()
        await self.symbol.info()
        tick = await self.symbol.info_tick()
        price = tick.ask if order_type == OrderType.BUY else tick.bid
        volume, sl = await self.symbol.compute_volume_sl(price=price, amount=amount, sl=sl, round_down=False,
                                                         use_limits=True)
        self.order.set_attributes(volume=volume, type=order_type, price=price, sl=sl, tp=tp,
                                  comment=self.parameters.get('name', self.__class__.__name__))

    async def place_trade(self, *, order_type: OrderType, sl: float, tp: float, parameters: dict = None):
        try:
            self.parameters |= parameters or {}

            if await self.check_ram() is False:
                logger.info(f'Could not place trade due to RAM for {self.symbol}')
                return

            await self.create_order(order_type=order_type, sl=sl, tp=tp)
            if await self.check_order() is False:
                return
            await self.send_order()
        except RuntimeError as _:
            pass
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.place_trade for {self.symbol}")
