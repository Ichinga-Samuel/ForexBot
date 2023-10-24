from aiomql import Trader, Positions, RAM, OrderType
from datetime import datetime
from symbols import CryptoSymbol, FXSymbol


class SingleTrader(Trader):
    """Only allows one position to be open at a time."""
    def __init__(self, symbol: CryptoSymbol | FXSymbol, ram: RAM = None):
        super().__init__(symbol=symbol, ram=ram)
        self.positions = Positions(symbol=symbol.name)
        self.ram = ram or RAM(risk=0.1, risk_to_reward=1)

    async def create_order(self, *, order_type: OrderType, **kwargs):
        res = await self.positions.positions_get()
        res.sort(key=lambda pos: pos.time_msc)
        loosing = [t for t in res if t.profit < 0]
        if len(loosing) > 3:
            raise RuntimeError(f"Last three trades in a losing position: {loosing[0].ticket}")
        pips = self.symbol.get_min_pips()
        self.order.comment = str(datetime.utcnow().timestamp())
        await super().create_order(order_type=order_type, pips=pips)
