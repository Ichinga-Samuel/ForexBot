from dataclasses import dataclass

from aiomql import Tracker as T


@dataclass
class Tracker(T):
    sl: float = 0
    tp: float = 0