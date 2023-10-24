from datetime import datetime

from aiomql import Trader, Positions, RAM, OrderType

from tele_bot import TelegramBot
from symbols import CryptoSymbol, FXSymbol


class ConfirmTrader(Trader):
    """Waits for manual confirmation from telegram before placing a trade."""
    def __init__(self, symbol: CryptoSymbol | FXSymbol, ram: RAM = None):
        super().__init__(symbol=symbol, ram=ram)
        self.positions = Positions(symbol=symbol.name)
        self.ram = ram or RAM(risk=0.1, risk_to_reward=2)
        self.tele_bot = TelegramBot()

    async def create_order(self, order_type: OrderType, **kwargs):
        res = await self.positions.positions_get()
        res.sort(key=lambda pos: pos.time_msc)
        loosing = [t for t in res if t.profit < 0]
        if len(loosing) > 3:
            raise RuntimeError(f"Last three trades in a losing position: {loosing[0].ticket}")
        pips = self.symbol.get_min_pips()
        volume = kwargs.get('volume', self.ram.volume) or await self.ram.get_volume(symbol=self.symbol, pips=pips)
        order = {'symbol': self.symbol.name, 'order_type': order_type, 'pips': pips, 'volume': volume,
                 'risk_to_reward': self.ram.risk_to_reward}

        self.ram.risk_to_reward = order['risk_to_reward']
        order = await self.tele_bot.confirm_order(order=order)
        self.order.volume = order['volume']
        self.order.type = order['order_type']
        self.order.comment = str(datetime.utcnow().timestamp())
        await self.set_order_limits(pips=order['pips'])
