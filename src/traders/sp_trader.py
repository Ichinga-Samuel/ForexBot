from logging import getLogger

from aiomql import OrderType, OrderSendResult

from .base_trader import BaseTrader

logger = getLogger(__name__)


class SPTrader(BaseTrader):

    def save_profit(self, result: OrderSendResult, profit):
        try:
            trailer = {"params": self.parameters, "prev_profit": 0, "expected_profit": profit, "extend_profit": 0.75}
            fixed_closer = {'close': False, 'cut_off': -1, 'close_adjust': 0.5} | self.fixed_closer
            self.config.state['atr_trailer'][result.order] = trailer
            self.config.state['fixed_closer'][result.order] = fixed_closer
            self.config.state['no_hedge'].append(result.order)
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.save_profit")

    async def create_order(self, *, order_type: OrderType, sl: float):
        self.ram.max_amount = 5
        self.ram.min_amount = 2.5
        self.ram.risk_to_reward = 1.5
        amount = await self.ram.get_amount()
        await self.symbol.info()
        tick = await self.symbol.info_tick()
        price_diff = tick.ask - sl if order_type == OrderType.BUY else sl - tick.bid
        points = price_diff / self.symbol.point
        min_points = self.symbol.trade_stops_level + self.symbol.spread
        if points < min_points:
            points = min_points
            logger.warning(f"Points adjusted to {points} for {self.symbol}")
        await self.create_order_points(order_type=order_type, points=points, amount=amount, use_limits=True,
                                       round_down=False, adjust=False)
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
            logger.error(f"{err} in {self.__class__.__name__}.place_trade for {self.symbol}")
