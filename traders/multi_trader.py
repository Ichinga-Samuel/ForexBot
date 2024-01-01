from logging import getLogger
import asyncio

from aiomql import Trader, Positions, RAM, OrderType, ForexSymbol

from telebots import TelegramBot
from symbols import FXSymbol

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
        self.ram = ram or RAM(risk=0.1, risk_to_reward=2)
        self.tele_bot = TelegramBot(order_format=self.order_format)
        self.tps = []
        self.rrs = [0.8, 1, 1.5]

    async def create_order(self, order_type: OrderType, sl: float):
        positions = await self.positions.positions_get()
        positions.sort(key=lambda pos: pos.time_msc)
        loosing = [trade for trade in positions if trade.profit < 0]
        if (losses := len(loosing)) > 4:
            raise RuntimeError(f"Last {losses} trades in a losing position")
        self.order.type = order_type
        await self.set_trade_stop_levels(sl=sl)
        amount = self.ram.amount or await self.ram.get_amount()
        # volume = await self.symbol.compute_volume(points=self.ram.points, amount=amount, use_limits=True)
        volume = self.symbol.volume_min
        order = {'symbol': self.symbol.name, 'order_type': int(order_type), 'points': self.ram.points, 'volume': volume,
                 'risk_to_reward': self.ram.risk_to_reward, 'strategy': self.parameters.get('name', 'None'),
                 'amount': amount, 'sl': self.order.sl, 'tp': self.order.tp}
        await self.tele_bot.notify(order=order)
        self.order.volume = volume
        self.order.comment = self.parameters.get('name', 'None')

    async def set_trade_stop_levels(self, *, sl: float):
        tick = await self.symbol.info_tick()
        self.order.sl = round(sl, self.symbol.digits)
        if self.order.type == OrderType.BUY:
            points = tick.ask - sl
            self.tps = [round(tick.ask + (points*rr), self.symbol.digits) for rr in self.rrs]
            self.order.tp = self.tps[0]
            self.order.price = tick.ask
        else:
            points = sl - tick.bid
            self.tps = [round(tick.bid + (points * rr), self.symbol.digits) for rr in self.rrs]
            self.order.tp = self.tps[0]
            self.order.price = tick.bid
        self.ram.points = points / self.symbol.point

    async def _send_order(self, tp):
        try:
            self.order.tp = tp
            self.parameters.update({'tp': tp})
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}._send_order")

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
            await asyncio.gather(*(self._send_order(tp) for tp in self.tps))
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")