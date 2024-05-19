from logging import getLogger
from functools import cache

from aiomql import OrderType, Trader, ForexSymbol, OrderSendResult
from ..utils.ram import RAM
from ..utils.order_utils import calc_loss
from ..closers.track_order import OpenOrder
from ..closers.trailing_profit import trail_tp
from ..closers.trailing_loss import trail_sl
from ..closers.check_profits import fixed_check_profit
from ..closers.hedge import hedge_position, track_hedge
from ..telebots import TelegramBot

logger = getLogger(__name__)


class BaseTrader(Trader):
    track_profit_params = {'trail_start': 15, 'trail': 4, 'trailing': False,
                           'extend_start': 0.8, 'start_trailing': True, 'extend_by': 4, 'adjust': 1.5,
                           'previous_profit': 0}
    track_loss_params = {'trail_start': 0.8, 'sl_limit': 15, 'trail': 2, 'trailing': True,
                         'previous_profit': 0}
    check_profit_params = {'close': False, 'check_point': -1, 'use_check_points': True,
                           "check_points": {12: 8, 16: 13, 22: 18, 10: 7, 7: 4, 4: 1}, 'adjust': 1.5}
    hedger_params = {'hedge_point': 0.58, 'hedge_cutoff': 0, 'hedge_vol': 1, 'adjust': 1.5}
    open_trades: list[int]
    order_format = """symbol: {symbol}\ntype: {type}\nvolume: {volume}\nsl: {sl}\ntp: {tp}
                   \rHint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} seconds from now.
                   \rNo reply will be considered as 'cancel'."""

    def __init__(self, *, symbol: ForexSymbol, ram: RAM = None,
                 use_telegram: bool = False, use_ram: bool = True, track_profit_params: dict = None,
                 track_loss_params: dict = None, hedge_order: bool = True, track_profit: bool = True,
                 use_exit_signal: bool = False, track_loss: bool = False, check_profit: bool = True,
                 check_profit_params: dict = None, track_orders: bool = True, hedger_params: dict = None,
                 profit_tracker=None, loss_tracker=None, profit_checker=None, hedger=None, hedge_tracker=None,
                 **kwargs):
        ram = ram or RAM(risk_to_reward=3, risk=0.01)
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
        self.profit_tracker = profit_tracker or trail_tp
        self.loss_tracker = loss_tracker or trail_sl
        self.profit_checker = profit_checker or fixed_check_profit
        self.hedger = hedger or hedge_position
        self.hedge_tracker = hedge_tracker or track_hedge
        super().__init__(symbol=symbol, ram=ram)

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
            order = OpenOrder(ticket=result.order, use_exit_signal=self.use_exit_signal, hedge_order=self.hedge_order,
                              track_loss=self.track_loss, track_profit=self.track_profit,
                              check_profit=self.check_profit, profit_checker=self.profit_checker, hedger=self.hedger,
                              profit_tracker=self.profit_tracker, loss_tracker=self.loss_tracker,
                              hedge_tracker=self.hedge_tracker, strategy_parameters=self.parameters.copy())

            if self.use_exit_signal and (exit_function := self.parameters.get('exit_function')) is not None:
                order.exit_function = exit_function

            if self.hedge_order:
                order.hedger_params = self.hedger_params.copy()

            if self.track_profit:
                order.track_profit_params = self.track_profit_params.copy()

            if self.track_loss:
                order.track_loss_params = self.track_loss_params.copy()

            if self.check_profit:
                order.check_profit_params = self.check_profit_params.copy()

            self.config.state['order_tracker'][result.order] = order
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.track_order")

    async def check_ram(self):
        positions = await self.ram.get_open_positions(symbol=self.symbol.name)
        self.open_trades = [position.ticket for position in positions if position.ticket in self.open_trades]
        if len(self.open_trades) >= self.ram.symbol_limit:
            raise RuntimeError(f"Exceeds limit of open position for {self.symbol} in {self.__class__.__name__}")

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
            profit = await self.order.calc_profit()
            loss = calc_loss(sym=self.symbol, open_price=self.order.price, close_price=self.order.sl,
                             volume=self.order.volume, order_type=self.order.type)
            self.hedger_params['loss'] = abs(loss)
            self.track_loss_params['expected_loss'] = abs(loss)
            self.track_profit_params['expected_profit'] = profit
            self.track_order(result=res)
            await self.notify(msg=f"Placed Trade for {self.symbol}")
            self.open_trades.append(res.order)
        return res

    async def place_trade(self, *args, **kwargs):
        """Places a trade based on the order_type."""
        raise NotImplementedError
