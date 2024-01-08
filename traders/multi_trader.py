from logging import getLogger
import asyncio

from aiomql import Trader, Positions, RAM, OrderType, ForexSymbol

from symbols import FXSymbol
from .ram import RAM

logger = getLogger(__name__)


class MultiTrader(Trader):
    """Place Multiple trades at once with different risk to reward ratios"""
    order_format = "symbol: {symbol}\norder_type: {order_type}\npoints: {points}\namount: {amount}\n" \
                   "volume: {volume}\nrisk_to_reward: {risk_to_reward}\nstrategy: {strategy}\n" \
                   "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} " \
                   "seconds from now. No reply will be considered as 'cancel'\n" \
                   "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    def __init__(self, symbol: ForexSymbol | FXSymbol, ram: RAM = None):
        super().__init__(symbol=symbol, ram=ram)
        self.positions = Positions(symbol=symbol.name)
        self.rrs = [0.55, 1, 1.2]
        self.tps = []
        self.ram = ram or RAM(risk=0.2, risk_to_reward=self.rrs[-1], points=0)

    async def create_order(self, order_type: OrderType):
        positions = await self.positions.positions_get()
        positions.sort(key=lambda pos: pos.time_msc)
        loosing = [trade for trade in positions if trade.profit < 0]
        if (losses := len(loosing)) > 4:
            raise RuntimeError(f"Last {losses} trades in a losing position")
        self.order.type = order_type
        amount = self.ram.amount or await self.ram.get_amount()
        points = self.ram.points or self.symbol.trade_stops_level * 2
        volume = await self.symbol.compute_volume(points=points, amount=amount)
        self.order.volume = volume
        self.order.comment = self.parameters.get('name', 'None')
        await self.set_trade_stop_levels(points=points)

    async def set_trade_stop_levels(self, *, points):
        """Set the stop loss and take profit levels of the order based on the points.
        Args:
            points: Target points
        """
        points = points * self.symbol.point
        sl = tp = points
        tick = await self.symbol.info_tick()
        if self.order.type == OrderType.BUY:
            self.order.sl = round(tick.ask - sl, self.symbol.digits)
            self.order.price = tick.ask
            self.tps = [round(tick.ask + tp * rr, self.symbol.digits) for rr in self.rrs]
            self.order.tp = self.tps[-1]
        else:
            self.order.sl = round(tick.bid + sl, self.symbol.digits)
            self.order.price = tick.bid
            self.tps = [round(tick.bid - tp * rr, self.symbol.digits) for rr in self.rrs]
            self.order.tp = self.tps[-1]

    async def _send_order(self, tp):
        try:
            self.order.tp = tp
            self.parameters.update({'tp': tp})
            # await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}._send_order")

    async def place_trade(self, order_type: OrderType, parameters: dict = None):
        """Places a trade based on the order_type.
        Args:
            order_type (OrderType): Type of order
            parameters: parameters of the trading strategy used to place the trade
        """
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type)
            if not await self.check_order():
                return
            # await asyncio.gather(*(self._send_order(tp) for tp in self.tps))
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")