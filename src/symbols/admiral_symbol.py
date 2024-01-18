from logging import getLogger

from aiomql import ForexSymbol

logger = getLogger(__name__)


class AdmiralSymbol(ForexSymbol):
    """Subclass of ForexSymbol for Admiral Markets Symbols. Handles the conversion of currency.
    """
    async def currency_conversion(self, *, amount: float, base: str, quote: str) -> float:
        """Convert from one currency to the other.

        Args:
            amount: amount to convert given in terms of the quote currency
            base: The base currency of the pair
            quote: The quote currency of the pair

        Returns:
            float: Amount in terms of the base currency

        Raises:
            ValueError: If conversion is impossible
        """
        try:
            pair = f'{base}{quote}-T'
            if self.account.has_symbol(pair):
                tick = await self.info_tick(name=pair)
                if tick is not None:
                    return amount / tick.ask

            pair = f'{quote}{base}-T'
            if self.account.has_symbol(pair):
                tick = await self.info_tick(name=pair)
                if tick is not None:
                    return amount * tick.bid
        except Exception as err:
            logger.warning(f'Currency conversion failed: Unable to convert {amount} in {quote} to {base}')
            raise ValueError(f'Currency Conversion Failed: {err}')
        else:
            logger.warning(f'Currency conversion failed: Unable to convert {amount} in {quote} to {base}')