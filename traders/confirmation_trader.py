from datetime import datetime
from logging import getLogger

from aiomql import Trader, Positions, RAM, OrderType, ForexSymbol, SingleTrader

from tele_bot import TelegramBot
from symbols import FXSymbol

logger = getLogger(__name__)


class ConfirmationTrader(Trader):
    """Waits for manual confirmation from telegram before placing a trade."""
    order_format = "symbol: {symbol}\norder_type: {order_type}\npoints: {points}\namount: {amount}\n" \
                   "volume: {volume}\nrisk_to_reward: {risk_to_reward}\nstrategy: {strategy}" \
                   "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} " \
                   "seconds from now. No reply will be considered as 'cancel'\n" \
                   "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    def __init__(self, symbol: ForexSymbol | FXSymbol, ram: RAM = None):
        super().__init__(symbol=symbol, ram=ram)
        self.positions = Positions(symbol=symbol.name)
        self.ram = ram or RAM(risk=0.1, risk_to_reward=2)
        self.tele_bot = TelegramBot(order_format=self.order_format)

    async def create_order(self, order_type: OrderType, points: float = 0, volume: float = 0):
        positions = await self.positions.positions_get()
        positions.sort(key=lambda pos: pos.time_msc)
        loosing = [trade for trade in positions if trade.profit < 0]
        if (losses := len(loosing)) > 3:
            raise RuntimeError(f"Last {losses} trades in a losing position")
        points = points or self.symbol.trade_stops_level + self.symbol.spread
        amount = self.ram.amount or await self.ram.get_amount()
        self.order.volume = await self.symbol.compute_volume(amount=amount, points=points)
        order = {'symbol': self.symbol.name, 'order_type': order_type, 'points': points, 'volume': volume,
                 'risk_to_reward': self.ram.risk_to_reward, 'strategy': self.parameters.get('name', 'None'),
                 'amount': amount}
        order = await self.tele_bot.confirm_order(order=order)
        if amount != order['amount']:
            volume = await self.symbol.compute_volume(amount=order['amount'], points=order['points'])
            order['volume'] = volume
        self.ram.risk_to_reward = order['risk_to_reward']
        self.order.volume = order['volume']
        self.order.type = order['order_type']
        self.order.comment = str(datetime.utcnow().timestamp())
        await self.set_trade_stop_levels(points=order['points'])

    async def place_trade(self, order_type: OrderType, parameters: dict = None, points: float = 0):
        """Places a trade based on the order_type.

        Args:
            order_type (OrderType): Type of order
            parameters: parameters of the trading strategy used to place the trade
            points (float): Target points
        """
        try:
            await self.create_order(order_type=order_type, points=points)
            if not await self.check_order():
                return
            self.parameters |= (parameters or {})
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")