from aiomql import Candle


def flat_top(*, first: Candle, second: Candle, tolerance=0.005) -> bool:
    bb = first.is_bullish() and second.is_bearish()
    cp = 1 - min(first.close, second.open) / max(first.close, second.open) <= tolerance
    return bb and cp


def flat_bottom(*, first: Candle, second: Candle, tolerance=0.005) -> bool:
    bb = first.is_bearish() and second.is_bullish()
    cp = 1 - min(first.close, second.open) / max(first.close, second.open) <= tolerance
    return bb and cp


def double_top(*, first: Candle, second: Candle, tolerance=0.005) -> bool:
    bb = first.is_bullish() and second.is_bearish()
    cp = 1 - min(first.close, second.open) / max(first.close, second.open) <= tolerance
    # ch = 1 - min(first.close, first.high) / max(first.close, first.high) <= tolerance * 4
    # oh = 1 - min(second.open, second.high) / max(second.open, second.high) <= tolerance * 4
    return bb and cp


def double_bottom(*, first: Candle, second: Candle, tolerance=0.005) -> bool:
    bb = first.is_bearish() and second.is_bullish()
    cp = 1 - min(first.close, second.open) / max(first.close, second.open) <= tolerance
    # cl = 1 - min(first.close, first.low) / max(first.close, first.low) <= tolerance * 4
    # ol = 1 - min(second.open, second.low) / max(second.open, second.low) <= tolerance * 4
    return bb and cp
