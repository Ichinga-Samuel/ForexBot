from typing import Callable, NewType, TypeVar
from dataclasses import dataclass, asdict
from logging import getLogger

from aiomql import TradePosition

logger = getLogger(__name__)

OpenOrder = TypeVar('OpenOrder')

OrderTracker = NewType('OrderTracker', Callable[[TradePosition, OpenOrder], None])


@dataclass
class OpenOrder:
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

    @property
    def data(self) -> dict:
        return asdict(self)


class TrackOrder:
    order: OpenOrder

    def __init__(self, *, position: TradePosition):
        self.position = position
        self.order = self.position.config.state['order_tracker'][self.position.ticket]

    async def track(self):
        try:
            if self.position.profit < 0 and self.order.hedge_order and self.order.hedger is not None:
                await self.order.hedger(position=self.position, order=self.order)

            if self.order.hedged and self.order.hedged_order is not None:
                await self.order.hedge_tracker(position=self.position, order=self.order)

            if self.order.use_exit_signal and self.order.exit_function is not None:
                await self.order.exit_function(position=self.position, order=self.order)

            print('Using profit tracker')
            if self.position.profit > 0 and self.order.track_profit and self.order.profit_tracker is not None:
                await self.order.profit_tracker(position=self.position, order=self.order)

            print('Using loss tracker')
            if self.position.profit < 0 and self.order.track_loss and self.order.loss_tracker is not None:
                await self.order.loss_tracker(position=self.position, order=self.order)

            print('Using profit checker')
            if self.order.check_profit and self.order.profit_checker is not None:
                await self.order.profit_checker(position=self.position, order=self.order)
        except (KeyError, RuntimeError) as _:
            pass
