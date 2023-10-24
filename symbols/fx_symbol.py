from math import ceil, log10

from aiomql import ForexSymbol, VolumeError


class FXSymbol(ForexSymbol):
    async def compute_volume(self, *, amount: float, pips: float, use_limits: bool = False) -> float:
        if (base := self.currency_profit) != (quote := self.account.currency):
            amount = await self.currency_conversion(amount=amount, base=base, quote=quote)

        volume = amount / (self.pip * self.trade_contract_size * pips)
        step = ceil(abs(log10(self.volume_step)))
        volume = round(volume, step)
        if (volume < self.volume_min) or (volume > self.volume_max):
            raise VolumeError(f'Incorrect Volume. Computed Volume outside the range of permitted volumes')
        return volume

    def get_min_pips(self):
        return self.trade_stops_level / 10 + ((self.spread * 2) / 10)
