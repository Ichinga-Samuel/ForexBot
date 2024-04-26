from dataclasses import dataclass

from aiomql import Tracker as T


@dataclass
class Tracker(T):
    wait: float = 0
    etf_time: float = 0
    ftf_time: float = 0
    stf_time: float = 0
