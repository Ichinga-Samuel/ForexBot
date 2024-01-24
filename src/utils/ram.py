from aiomql import RAM as _RAM, Positions


class RAM(_RAM):
    min_amount: float = 4
    max_amount: float = 12
    loss_limit: int = 3
    balance_level: float = 100

    async def get_amount(self) -> float:
        amount = await super().get_amount()
        return max(self.min_amount, min(self.max_amount, amount))