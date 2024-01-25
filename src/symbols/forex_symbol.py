from aiomql import ForexSymbol as FS


class ForexSymbol(FS):
    """Forex symbol."""

    def compute_points_2(self, *, amount: float) -> float:
        """Compute points. Using the amount and the minimum volume."""
        points = amount / (self.volume_min * self.point * self.trade_contract_size)