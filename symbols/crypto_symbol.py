from math import log10, ceil

from aiomql import Symbol, VolumeError


class CryptoSymbol(Symbol):
    @property
    def pip(self):
        return self.point

    def check_volume(self, volume) -> tuple[bool, float]:
        check = self.volume_min <= volume <= self.volume_max
        if check:
            return check, volume
        if not check and volume < self.volume_min:
            return check, self.volume_min
        else:
            return check, self.volume_max

    def round_off_volume(self, volume):
        step = ceil(abs(log10(self.volume_step)))
        return round(volume, step)

    async def compute_volume(self, *, amount: float, pips: float, use_limits: bool = False) -> float:
        volume = amount / (self.pip * pips)
        volume = self.round_off_volume(volume)
        if self.check_volume(volume)[0]:
            return volume
        raise VolumeError(f'Incorrect Volume. Computed Volume outside the range of permitted volumes')

    def get_min_pips(self):
        """Get minimum tradeable pips"""
        return self.trade_stops_level + (self.spread * 2)
