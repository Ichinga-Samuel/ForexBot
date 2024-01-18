from aiomql import RAM as _RAM


class RAM(_RAM):
    min_amount: float = 3
    max_amount: float = 4

    async def get_amount(self, risk: float = 0) -> float:
        amount = await super().get_amount(risk=risk)
        return max(self.min_amount, min(self.max_amount, amount))