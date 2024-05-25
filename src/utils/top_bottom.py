from aiomql import Candle


def flat_top(*, first: Candle, second: Candle, tolerance=0.01) -> bool:
    return (first.is_bullish() and second.is_bearish()
            and (abs(first.close - second.open) / min(first.close, second.open) <= tolerance))


def flat_bottom(*, first: Candle, second: Candle, tolerance=0.01) -> bool:
    return (first.is_bearish() and second.is_bullish()
            and (abs(first.close - second.open) / min(first.close, second.open) <= tolerance))


def double_top(*, first: Candle, second: Candle, tolerance=0.01) -> bool:
    bb = first.is_bullish() and second.is_bearish()
    cp = abs(first.close - second.open) / min(first.close, second.open) <= tolerance
    ch = abs(first.close - first.high) / min(first.close, first.high) <= tolerance
    oh = abs(second.open - second.high) / min(second.open, second.high) <= tolerance
    return bb and cp and ch and oh


def double_bottom(*, first: Candle, second: Candle, tolerance=0.01) -> bool:
    bb = first.is_bearish() and second.is_bullish()
    cp = abs(first.close - second.open) / min(first.close, second.open) <= tolerance
    cl = abs(first.close - first.low) / min(first.close, first.low) <= tolerance
    ol = abs(second.open - second.low) / min(second.open, second.low) <= tolerance
    return bb and cp and cl and ol
