from mplfinance.original_flavor import candlestick_ohlc
from scipy.signal import argrelextrema

import matplotlib.dates as mpdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def draw_plot(ohlc, patterns, max_min):
    """
    Save the plots of the analysis

    :params ohlc -> dataframe holding the ohlc data

    :params patterns -> all the indices where the patterns exist

    :params max_min -> the maxima and minima

    :params filename -> prefix for the graph names
    """
    for i, pattern in enumerate(patterns):
        fig, ax = plt.subplots(figsize=(15, 7))
        start_ = pattern[0]
        end_ = pattern[1]
        idx = max_min.loc[start_ - 100:end_ + 100].index.values.tolist()
        ohlc_copy = ohlc.copy()
        ohlc_copy.loc[:, "Index"] = ohlc_copy.index

        max_min_idx = max_min.loc[start_:end_].index.tolist()

        candlestick_ohlc(ax, ohlc_copy.loc[idx, ["Index", "open", "high", "low", "close"]].values, width=0.1,
                         colorup='green', colordown='red', alpha=0.8)
        ax.plot(max_min_idx, max_min.loc[start_:end_].values[:, 1], color='orange')

        ax.grid(True)
        ax.set_xlabel('Index')
        ax.set_ylabel('Price')


def find_doubles_patterns(data, window_range, smooth=True, smoothing_period=10):
    """
    Find the double tops and bottoms patterns

    :params max_min -> the maxima and minima

    :return patterns_tops, patterns_bottoms
    """
    data["Date"] = pd.to_datetime(data["time"], unit='ms', origin='unix')
    data["Date"] = data["Date"].map(mpdates.date2num)
    max_min = find_local_maxima_minima(data, window_range, smooth=smooth, smoothing_period=smoothing_period)
    patterns_tops = []
    patterns_bottoms = []

    # Window range is 5 units
    for i in range(5, len(max_min)):
        window = max_min.iloc[i - 5:i]

        # Pattern must play out in less than n units
        if window.index[-1] - window.index[0] > 50:
            continue

        a, b, c, d, e = window.iloc[0:5, 1]
        # Double Tops
        if a < b and a < d and c < b and c < d and e < b and e < d and b > d:
            patterns_tops.append((window.index[0], window.index[-1]))

        # Double Bottoms
        if a > b and a > d and c > b and c > d and e > b and e > d and b < d:
            patterns_bottoms.append((window.index[0], window.index[-1]))

    return patterns_tops, patterns_bottoms


def find_local_maxima_minima(ohlc, window_range, smooth=False, smoothing_period=10):
    """
    Find all the local maxima and minima

    :params ohlc         -> dataframe holding the ohlc data
    :params window_range -> range to find min and max
    :params smooth       -> should the prices be smoothed
    :params smoothing_period -> the smoothing period

    :return max_min
    """
    local_max_arr = []
    local_min_arr = []

    if smooth:
        smooth_close = ohlc["close"].rolling(window=smoothing_period).mean().dropna()
        local_max = argrelextrema(smooth_close.values, np.greater)[0]
        local_min = argrelextrema(smooth_close.values, np.less)[0]
    else:
        local_max = argrelextrema(ohlc["close"].values, np.greater)[0]
        local_min = argrelextrema(ohlc["close"].values, np.less)[0]

    for i in local_max:
        if (i > window_range) and (i < len(ohlc) - window_range):
            local_max_arr.append(ohlc.iloc[i - window_range:i + window_range]['close'].idxmax())

    for i in local_min:
        if (i > window_range) and (i < len(ohlc) - window_range):
            local_min_arr.append(ohlc.iloc[i - window_range:i + window_range]['close'].idxmin())

    maxima = pd.DataFrame(ohlc.loc[local_max_arr])
    minima = pd.DataFrame(ohlc.loc[local_min_arr])
    max_min = pd.concat([maxima, minima]).sort_index()
    max_min = max_min[~max_min.index.duplicated()]

    return max_min
