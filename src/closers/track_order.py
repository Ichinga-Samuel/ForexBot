from typing import Callable, NewType, TypeVar
from dataclasses import dataclass
from copy import deepcopy
from logging import getLogger

from aiomql import TradePosition, Config

logger = getLogger(__name__)

OpenOrder = TypeVar('OpenOrder')

OrderTracker = NewType('OrderTracker', Callable[[OpenOrder], None])


@dataclass
class OpenOrder:
    symbol: str
    ticket: int
    use_exit_signal: bool
    hedge_order: bool
    track_loss: bool
    track_profit: bool
    check_profit: bool
    exit_function: OrderTracker = None
    profit_tracker: OrderTracker = None
    loss_tracker: OrderTracker = None
    profit_checker: OrderTracker = None
    hedger: OrderTracker = None
    hedge_tracker: OrderTracker = None
    track_profit_params: dict = None
    track_loss_params: dict = None
    check_profit_params: dict = None
    hedger_params: dict = None
    strategy_parameters: dict = None
    hedged: bool = False
    hedged_order: OpenOrder = None
    hedge_on_exit: bool = False
    hedge: OpenOrder = None
    expected_profit: float = 0.0
    expected_loss: float = 0.0
    target_profit: float = None
    target_loss: float = None
    position: TradePosition = None
    config: Config = Config()

    @property
    def data(self) -> dict:
        exclude = {'hedged_order', 'position', 'config', 'ticket'}
        return {k: deepcopy(v) for k, v in self.__dict__.items() if k not in exclude}

    def update(self, **kwargs):
        [setattr(self, key, value) for key, value in kwargs.items() if key in self.__dict__]


class TrackOrder:
    order: OpenOrder

    def __init__(self, *, order: OpenOrder):
        self.order = order

    async def track(self):
        try:
            if self.order.position.profit < 0 and self.order.hedge_order and self.order.hedger is not None:
                await self.order.hedger(order=self.order)

            if self.order.hedged and self.order.hedged_order is not None:
                await self.order.hedge_tracker(hedge=self.order)

            if self.order.use_exit_signal and self.order.exit_function is not None:
                await self.order.exit_function(order=self.order)

            if self.order.position.profit > 0 and self.order.track_profit and self.order.profit_tracker is not None:
                await self.order.profit_tracker(order=self.order)

            if self.order.position.profit < 0 and self.order.track_loss and self.order.loss_tracker is not None:
                await self.order.loss_tracker(order=self.order)

            if self.order.check_profit and self.order.profit_checker is not None:
                await self.order.profit_checker(order=self.order)
        except Exception as exe:
            logger.error(f"Error tracking order: {exe}: {exe.__traceback__.tb_lineno}")
