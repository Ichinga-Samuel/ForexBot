"""Trader class module. Handles the creation of an order and the placing of trades"""
from logging import getLogger

from aiomql import OrderType, Trader, ForexSymbol
from .ram import RAM

logger = getLogger(__name__)


class SimpleTrader(Trader):
    """A simple trader class. Limits the number of loosing trades per symbol"""
    def __init__(self, *, symbol: ForexSymbol, ram=RAM(risk_to_reward=1.5, points=0)):
        """Initializes the order object and RAM instance

        Args:
            symbol (Symbol): Financial instrument
            ram (RAM): Risk Assessment and Management instance
        """
        super().__init__(symbol=symbol, ram=ram)

    async def create_order(self, *, order_type: OrderType):
        """Complete the order object with the required values. Creates a simple order.

        Args:
            order_type (OrderType): Type of order
            points (float): Target points
        """
        points = self.ram.points or self.symbol.trade_stops_level * 3
        amount = await self.ram.get_amount()
        self.order.volume = await self.symbol.compute_volume(amount=amount, points=points)
        self.order.type = order_type
        self.order.comment = self.parameters.get('name', '')
        await self.set_trade_stop_levels(points=points)

    async def place_trade(self, order_type: OrderType, parameters: dict = None):
        """Places a trade based on the order_type."""
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")