from logging import getLogger
from functools import cache

from aiomql import OrderType, Trader, ForexSymbol, OrderSendResult
from ..utils.ram import RAM
from ..utils.order_utils import calc_profit
from ..closers.track_order import OpenOrder
from ..closers.atr_trailer import atr_trailer
from ..closers.trailing_loss import trail_sl
from ..closers.check_profits import ratio_check_profit
from ..closers.hedge import hedge_position, track_hedge_2
from ..telebots import TelegramBot

logger = getLogger(__name__)


class BaseTrader(Trader):
    track_profit_params = {'trail_start': 0.25, 'trail': 0.15, 'extend_start': 0.9, 'start_trailing': True,
                           'previous_profit': 0, "ce_period": 14}

    track_loss_params = {'trail_start': 0.95, 'sl_limit': 15, 'trail': 2, 'trailing': True,
                         'previous_profit': 0}

    check_profit_params = {'close': False, 'check_point': -1, 'use_check_points': True,
                           "check_points": {1.5: 1, 2: 1.5, 2.5: 2},
                           'hedge_adjust': 0.98, 'exit_adjust': 0.98}

    hedger_params = {'hedge_point': 0.90, 'hedge_close': 0.4, 'hedge_vol': 1, 'hedged_close': 0.05}
    open_trades: list[int]
    open_order: OpenOrder
    order_format = """symbol: {symbol}\ntype: {type}\nvolume: {volume}\nsl: {sl}\ntp: {tp}
                   \rHint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} seconds from now.
                   \rNo reply will be considered as 'cancel'."""

    def __init__(self, *, symbol: ForexSymbol, ram: RAM = None,
                 use_telegram: bool = False, use_ram: bool = True, track_profit_params: dict = None,
                 track_loss_params: dict = None, hedge_order: bool = False, track_profit: bool = True,
                 use_exit_signal: bool = True, track_loss: bool = False, check_profit: bool = True,
                 check_profit_params: dict = None, track_orders: bool = True, hedger_params: dict = None,
                 profit_tracker=None, loss_tracker=None, profit_checker=None, hedger=None, hedge_tracker=None,
                 hedge_on_exit: bool = False, **kwargs):

        ram = ram or RAM(risk_to_reward=2, risk=0.01)
        self.use_telegram = use_telegram
        self.use_exit_signal = use_exit_signal
        self.track_profit_params = self.track_profit_params | (track_profit_params or {})
        self.track_loss_params = self.track_loss_params | (track_loss_params or {})
        self.check_profit_params = self.check_profit_params | (check_profit_params or {})
        self.hedger_params = self.hedger_params | (hedger_params or {})
        self.track_loss = track_loss
        self.track_profit = track_profit
        self.check_profit = check_profit
        self.open_trades = []
        self.hedge_order = hedge_order
        self.use_ram = use_ram
        self.track_orders = track_orders
        self.profit_tracker = profit_tracker or atr_trailer
        self.loss_tracker = loss_tracker or trail_sl
        self.profit_checker = profit_checker or ratio_check_profit
        self.hedger = hedger or hedge_position
        self.hedge_tracker = hedge_tracker or track_hedge_2
        self.hedge_on_exit = hedge_on_exit
        super().__init__(symbol=symbol, ram=ram)
        self.open_order = OpenOrder(symbol=symbol.name, ticket=0, use_exit_signal=self.use_exit_signal,
                                    hedge_order=self.hedge_order, track_loss=self.track_loss,
                                    track_profit=self.track_profit, check_profit=self.check_profit,
                                    profit_checker=self.profit_checker, hedger=self.hedger,
                                    profit_tracker=self.profit_tracker, loss_tracker=self.loss_tracker,
                                    hedge_tracker=self.hedge_tracker, hedge_on_exit=self.hedge_on_exit,)

    @property
    @cache
    def telebot(self):
        token = getattr(self.config, 'telegram_bot_token', None)
        chat_id = getattr(self.config, 'telegram_chat_id', None)
        confirmation_timeout = getattr(self.config, 'confirmation_timeout', 90)
        return TelegramBot(token=token, chat_id=chat_id, confirmation_timeout=confirmation_timeout,
                           order_format=self.order_format)

    async def notify(self, msg: str = ''):
        try:
            if self.use_telegram and getattr(self.config, 'use_telegram', True):
                self.config.task_queue.add_task(self.telebot.notify, msg=msg)
        except Exception as err:
            logger.error(f"{err} for {self.order.symbol} in {self.__class__.__name__}.notify")

    async def confirm_order(self, *, order: dict = None, order_format: str = '') -> bool:
        try:
            if self.use_telegram and getattr(self.config, 'use_telegram', True):
                order = order or self.order.get_dict(include={'symbol', 'type', 'sl', 'volume', 'tp'})
                ok = await self.telebot.get_order_confirmation(order=order, order_format=order_format)
                return ok
            else:
                return True
        except Exception as err:
            logger.error(f"{err} for {self.order.symbol} in {self.__class__.__name__}.confirm_order")
            return False

    def track_order(self, *, result: OrderSendResult):
        try:
            if self.track_orders is False:
                return
            profit = result.profit or calc_profit(sym=self.symbol, open_price=self.order.price,
                                                  close_price=self.order.tp,
                                                  volume=self.order.volume, order_type=self.order.type)
            loss = result.loss or calc_profit(sym=self.symbol, open_price=self.order.price, close_price=self.order.sl,
                                              volume=self.order.volume, order_type=self.order.type)

            self.open_order.update(ticket=result.order, expected_loss=loss, expected_profit=profit,
                                   strategy_parameters=self.parameters.copy())

            if self.use_exit_signal and (exit_function := self.parameters.get('exit_function')) is not None:
                self.open_order.exit_function = exit_function

            if self.hedge_order:
                self.open_order.hedger_params = self.hedger_params.copy()

            if self.track_profit:
                self.open_order.track_profit_params = self.track_profit_params.copy()

            if self.track_loss:
                self.open_order.track_loss_params = self.track_loss_params.copy()

            if self.check_profit:
                self.open_order.check_profit_params = self.check_profit_params.copy()

            self.config.state['tracked_orders'][result.order] = self.open_order
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.track_order")

    async def check_ram(self) -> bool:
        if self.use_ram is False:
            return True
        positions = await self.ram.get_open_positions(symbol=self.symbol.name)
        self.open_trades = [position.ticket for position in positions if position.ticket in self.open_trades]
        return len(self.open_trades) < self.ram.symbol_limit

    async def create_order_points(self, order_type: OrderType, points: float = 0, amount: float = 0, **volume_kwargs):
        self.order.type = order_type
        volume, points = await self.symbol.compute_volume_points(amount=amount, points=points, **volume_kwargs)
        self.order.volume = volume
        self.order.comment = self.parameters.get('name', self.__class__.__name__)
        tick = await self.symbol.info_tick()
        self.set_trade_stop_levels(points=points, tick=tick)

    async def create_order_sl(self, order_type: OrderType, sl: float, amount: float, **volume_kwargs):
        tick = await self.symbol.info_tick()
        price = tick.ask if order_type == OrderType.BUY else tick.bid
        volume, sl = await self.symbol.compute_volume_sl(price=price, amount=amount, sl=sl, **volume_kwargs)
        points = abs(sl - price) / self.symbol.point
        self.order.set_attributes(volume=volume, type=order_type,
                                  comment=self.parameters.get('name', self.__class__.__name__))
        self.set_trade_stop_levels(points=points, tick=tick)

    async def send_order(self) -> OrderSendResult:
        ok = await self.confirm_order()
        if not ok:
            raise RuntimeError("Order not confirmed")
        res = await super().send_order()
        if res.retcode == 10009:
            await self.notify(msg=f"Placed Trade for {self.symbol}")
            self.open_trades.append(res.order)
            self.track_order(result=res)
            name = self.parameters.get('name', self.__class__.__name__)
            await self.record_trade(res, name=f"{name}_{self.config.login}", exclude={'exit_function'})
        return res

    async def place_trade(self, *args, **kwargs):
        """Places a trade based on the order_type."""
        raise NotImplementedError
