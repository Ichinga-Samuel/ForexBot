from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader
from ..utils.ram import RAM

logger = getLogger(__name__)


class SPTrader(BaseTrader):
    def __init__(self, *, symbol, hedge_order=True, track_loss=True, **kwargs):
        ram = RAM(risk_to_reward=2, risk=0.1)
        ram = kwargs.pop('ram', ram)
        super().__init__(symbol=symbol, hedge_order=hedge_order, track_loss=track_loss, ram=ram, **kwargs)

    async def create_order(self, *, order_type: OrderType, sl: float, tp: float):
        amount = await self.ram.get_amount()
        await self.symbol.info()
        tick = await self.symbol.info_tick()
        price = tick.ask if order_type == OrderType.BUY else tick.bid
        volume, sl = await self.symbol.compute_volume_sl(price=price, amount=amount, sl=sl, round_down=True,
                                                         use_limits=True, adjust=False)
        self.open_order.target_loss = amount * -1
        self.open_order.target_profit = amount * self.ram.risk_to_reward
        self.order.set_attributes(volume=volume, type=order_type, price=price, sl=sl, tp=tp,
                                  comment=self.parameters.get('name', self.__class__.__name__))

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
