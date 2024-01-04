from logging import getLogger

from aiomql import Trader, Positions, RAM, OrderType, ForexSymbol

from .ram import RAM
from telebots import TelegramBot
from symbols import FXSymbol

logger = getLogger(__name__)


class FXTrader(Trader):
    """Send a notification to a telegram bot before placing a trade"""
    order_format = "symbol: {symbol}\norder_type: {order_type}\npoints: {points}\namount: {amount}\n" \
                   "volume: {volume}\nrisk_to_reward: {risk_to_reward}\nstrategy: {strategy}\n" \
                   "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} " \
                   "seconds from now. No reply will be considered as 'cancel'\n" \
                   "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    def __init__(self, symbol: ForexSymbol | FXSymbol, ram: RAM = None, loss_limit: int = 3):
        super().__init__(symbol=symbol, ram=ram)
        self.ram = ram or RAM(risk=0.03, risk_to_reward=1.5)
        self.tele_bot = TelegramBot(order_format=self.order_format)
        self.loss_limit = loss_limit

    async def create_order(self, order_type: OrderType, sl: float):
        positions = await Positions().positions_get()
        loosing = [trade for trade in positions if trade.profit < 1]
        if (losses := len(loosing)) > self.loss_limit:
            raise RuntimeError(f"Last {losses} trades in a losing position")

        self.order.type = order_type
        await self.set_trade_stop_levels(sl=sl)
        amount = self.ram.amount or await self.ram.get_amount()
        volume = await self.symbol.compute_volume(points=self.ram.points, amount=amount)
        order = {'symbol': self.symbol.name, 'order_type': int(order_type), 'points': self.ram.points, 'volume': volume,
                 'risk_to_reward': self.ram.risk_to_reward, 'strategy': self.parameters.get('name', 'None'),
                 'amount': amount}
        # await self.tele_bot.notify(order=order)
        self.order.volume = volume
        self.order.comment = self.parameters.get('name', 'None')

    async def set_trade_stop_levels(self, *, sl: float):
        tick = await self.symbol.info_tick()
        self.order.sl = round(sl, self.symbol.digits)
        if self.order.type == OrderType.BUY:
            points = tick.ask - sl
            tp = points * self.ram.risk_to_reward
            self.order.tp = round(tick.ask + tp, self.symbol.digits)
            self.order.price = tick.ask
        else:
            points = sl - tick.bid
            tp = points * self.ram.risk_to_reward
            self.order.tp = round(tick.bid - tp, self.symbol.digits)
            self.order.price = tick.bid
        self.ram.points = points / self.symbol.point

    async def place_trade(self, order_type: OrderType, parameters: dict = None, sl: float = 0):
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, sl=sl)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")