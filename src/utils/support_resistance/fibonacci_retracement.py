from pandas import DataFrame
from numpy import sqrt


def fib_ret(*, data: DataFrame, fibs: list = None):
    fibs = fibs or [sqrt(55/89), 34/89, 0.5, 21/89]
    low, high = data['close'].min(), data['close'].max()

    diff = high - low
    down_trend_retracement = {f"fib{round(fib*1000)}": (low + fib * diff) for fib in fibs}
    down_trend_retracement['fib100'] = high
    down_trend_retracement['fib0'] = low
    up_trend_retracement = {f"fib{round(fib*1000)}": (high - fib * diff) for fib in fibs}
    up_trend_retracement['fib100'] = low
    up_trend_retracement['fib0'] = high
    return {"down_trend_retracement": down_trend_retracement, "up_trend_retracement": up_trend_retracement}
