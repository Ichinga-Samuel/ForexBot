from dataclasses import dataclass

from aiomql import Tracker as T


@dataclass
class Tracker(T):
    wait: float = 0
