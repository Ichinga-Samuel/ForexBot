from aiomql import RAM as _RAM, Positions, TradePosition


class RAM(_RAM):
    min_amount: float = 5
    max_amount: float = 100
    loss_limit: int = 5
    symbol_limit: int = 1
    open_limit: int = 10
    fixed_amount: float = None
    balance_level: float = 50
    positions: list[TradePosition]

    async def get_amount(self) -> float:
        if self.fixed_amount:
            return self.fixed_amount
        await self.account.refresh()
        amount = self.account.equity * self.risk
        return max(self.min_amount, min(self.max_amount, amount))

    async def get_open_positions(self, symbol='') -> list[TradePosition]:
        pos = await Positions(symbol=symbol).positions_get()
        self.positions = pos
        return pos

    async def check_losing_positions(self, symbol='') -> bool:
        """Check if the number of losing positions is greater than or equal the loss limit."""
        positions = await Positions(symbol=symbol).positions_get()
        loosing = [trade for trade in positions if trade.profit < 0]
        return len(loosing) > self.loss_limit

    async def check_symbol_positions(self, *, symbol) -> bool:
        positions = await Positions(symbol=symbol).positions_get()
        # loosing = [trade for trade in positions if trade.profit < 0]
        return len(positions) >= self.symbol_limit

    async def check_open_positions(self, symbol='') -> bool:
        """Check if the number of open positions is greater than or equal the loss limit."""
        positions = await Positions(symbol=symbol).positions_get()
        return len(positions) >= self.open_limit
