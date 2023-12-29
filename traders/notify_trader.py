from datetime import datetime
from logging import getLogger

from aiomql import Trader, Positions, RAM, OrderType, ForexSymbol

from telebots import TelegramBot
from symbols import FXSymbol

logger = getLogger(__name__)


class NotifyVTrader(Trader):
    """Waits for manual confirmation from telegram before placing a trade."""
    order_format = "symbol: {symbol}\norder_type: {order_type}\npoints: {points}\namount: {amount}\n" \
                   "volume: {volume}\nrisk_to_reward: {risk_to_reward}\nstrategy: {strategy}\n" \
                   "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} " \
                   "seconds from now. No reply will be considered as 'cancel'\n" \
                   "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    def __init__(self, symbol: ForexSymbol | FXSymbol, ram: RAM = None):
        super().__init__(symbol=symbol, ram=ram)
        self.positions = Positions(symbol=symbol.name)
        self.ram = ram or RAM(risk=0.1, risk_to_reward=2)
        self.tele_bot = TelegramBot(order_format=self.order_format)

    async def create_order(self, order_type: OrderType, sl: float):
        positions = await self.positions.positions_get()
        positions.sort(key=lambda pos: pos.time_msc)
        loosing = [trade for trade in positions if trade.profit < 0]
        if (losses := len(loosing)) > 4:
            raise RuntimeError(f"Last {losses} trades in a losing position")
        self.order.type = order_type
        await self.set_trade_stop_levels(sl=sl)
        amount = self.ram.amount or await self.ram.get_amount()
        volume = await self.symbol.compute_volume(points=self.ram.points, amount=amount)
        order = {'symbol': self.symbol.name, 'order_type': int(order_type), 'points': self.ram.points, 'volume': volume,
                 'risk_to_reward': self.ram.risk_to_reward, 'strategy': self.parameters.get('name', 'None'),
                 'amount': amount}
        await self.tele_bot.notify(order=order)
        self.order.volume = volume
        self.order.comment = self.parameters.get('name', 'None')

    async def set_trade_stop_levels(self, *, sl: float):
        tick = await self.symbol.info_tick()
        if self.order.type == OrderType.BUY:
            points = tick.ask - sl
            tp = points * self.ram.risk_to_reward
            self.order.sl, self.order.tp = round(sl, self.symbol.digits), round(tick.ask + tp, self.symbol.digits)
            self.order.price = tick.ask
        else:
            points = sl - tick.bid
            tp = points * self.ram.risk_to_reward
            self.order.sl, self.order.tp = round(sl, self.symbol.digits), round(tick.bid - tp, self.symbol.digits)
            self.order.price = tick.bid * points
        self.ram.points = points / self.symbol.point

    async def place_trade(self, order_type: OrderType, parameters: dict = None, sl: float = 0):
        """Places a trade based on the order_type.
        Args:
            order_type (OrderType): Type of order
            parameters: parameters of the trading strategy used to place the trade
            :param sl:
        """
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, sl=sl)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")