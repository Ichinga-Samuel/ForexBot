from aiomql import Candle, Candles


def find_bearish_fractal(candles: Candles) -> Candle | None:
    for i in reversed(range(2, len(candles) - 1)):
        if candles[i].high > max(candles[i - 1].high, candles[i + 1].high):
            return candles[i]


def find_bullish_fractal(candles: Candles) -> Candle | None:
    for i in reversed(range(2, len(candles) - 1)):
        if candles[i].low < min(candles[i - 1].low, candles[i + 1].low):
            return candles[i]


# def find_bearish_fractal(candles: Candles) -> Candle | None:
#     for i in reversed(range(2, len(candles) - 2)):
#         if candles[i].high > max(candles[i - 2].high, candles[i - 1].high, candles[i + 1].high,
#                                  candles[i + 2].high):
#             return candles[i]
#
#
# def find_bullish_fractal(candles: Candles) -> Candle | None:
#     for i in reversed(range(2, len(candles) - 2)):
#         if candles[i].low < min(candles[i - 2].low, candles[i - 1].low, candles[i + 1].low,
#                                 candles[i + 2].low):
#             return candles[i]