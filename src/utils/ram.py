from aiomql import RAM as _RAM, Positions


class RAM(_RAM):
    min_amount: float = 5
    max_amount: float = 5
    loss_limit: int = 3
    balance_level: float = 50

    async def get_amount(self) -> float:
        await self.account.refresh()
        amount = self.account.margin_free * self.risk
        return max(self.min_amount, min(self.max_amount, amount))

    async def check_losing_positions(self, symbol='') -> bool:
        """Check if the number of losing positions is greater than or equal the loss limit."""
        positions = await Positions(symbol=symbol).positions_get()
        positions.sort(key=lambda pos: pos.time_msc)
        # loosing = [trade for trade in positions if trade.profit <= 0]
        return len(positions) >= self.loss_limit

    async def check_open_positions(self, symbol='') -> bool:
        """Check if the number of open positions is greater than or equal the loss limit."""
        positions = await Positions(symbol=symbol).positions_get()
        # positions.sort(key=lambda pos: pos.time_msc)
        return len(positions) >= self.loss_limit
