from aiomql import Candle


def flat_top(*, first: Candle, second: Candle, tolerance=0.01) -> bool:
    return (first.is_bullish() and second.is_bearish()
            and abs(first.close - second.open) / min(first.close, second.open) <= tolerance)


def flat_bottom(*, first: Candle, second: Candle, tolerance=0.01) -> bool:
    return (first.is_bearish() and second.is_bullish()
            and abs(first.close - second.open) / min(first.close, second.open) <= tolerance)
