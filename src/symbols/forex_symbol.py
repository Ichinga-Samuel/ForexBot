from aiomql import ForexSymbol as FS


class ForexSymbol(FS):
    """Forex symbol."""

    def compute_points_2(self, *, amount: float) -> float:
        """Compute points. Using the amount and the minimum volume."""
        points = amount / (self.volume_min * self.point * self.trade_contract_size)
        return points

    def check_volume(self, volume) -> tuple[bool, float]:
        """Check if the volume is within the limits of the symbol. If not, return the nearest limit.

        Args:
            volume (float): Volume to check

        Returns: tuple[bool, float]: Returns a tuple of a boolean and a float. The boolean indicates if the volume is
        within the limits of the symbol. The float is the volume to use if the volume is not within the limits of the
        symbol.
        """
        check = self.volume_min <= volume <= self.volume_max
        if check:
            return check, volume
        if volume < self.volume_min:
            return check, self.volume_min
        else:
            return check, self.volume_max
