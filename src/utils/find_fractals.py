from aiomql import Candle, Candles


class Fractal:
    middle: Candle
    first_left: Candle
    first_right: Candle
    second_left: Candle
    second_right: Candle


def find_bearish_fractals(candles: Candles, count: int = 2) -> list[Fractal]:
    fractals = []
    for i in range(len(candles) - 3, 1, -1):
        if candles[i].high > max(candles[i - 1].high, candles[i + 1].high, candles[i - 2].high, candles[i + 2].high):
            fractal = Fractal()
            fractal.middle = candles[i]
            fractal.first_left = candles[i - 1]
            fractal.first_right = candles[i + 1]
            fractal.second_left = candles[i - 2]
            fractal.second_right = candles[i + 2]
            fractals.append(fractal)
        if len(fractals) == count:
            return fractals


def find_bullish_fractals(candles: Candles, count: int = 2) -> list[Fractal]:
    fractals = []
    for i in range(len(candles) - 3, 1, -1):
        if candles[i].low < min(candles[i - 1].low, candles[i + 1].low, candles[i - 2].low, candles[i + 2].low):
            fractal = Fractal()
            fractal.middle = candles[i]
            fractal.first_left = candles[i - 1]
            fractal.first_right = candles[i + 1]
            fractal.second_left = candles[i - 2]
            fractal.second_right = candles[i + 2]
            fractals.append(fractal)
        if len(fractals) == count:
            return fractals
