from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader
from ..closers.atr_trailer import atr_trailer
from ..closers.check_profits import ratio_check_profit

logger = getLogger(__name__)


class SPTrader(BaseTrader):
    def __init__(self, *, symbol, ram, hedge_order=False, profit_tracker=atr_trailer,
                 profit_checker=ratio_check_profit, **kwargs):
        check_profit_params = {'use_check_points': False} | kwargs.pop('check_profit_params', {})
        super().__init__(symbol=symbol, ram=ram, hedge_order=hedge_order, profit_tracker=profit_tracker,
                         check_profit_params=check_profit_params, profit_checker=profit_checker, **kwargs)

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
            if self.use_ram:
                await self.check_ram()
            await self.create_order(order_type=order_type, sl=sl, tp=tp)
            if not await self.check_order():
                return
            await self.send_order()
        except RuntimeError as _:
            pass
        except Exception as err:
            logger.error(f"{err} in {self.__class__.__name__}.place_trade for {self.symbol}")
