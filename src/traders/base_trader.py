from logging import getLogger
from functools import cache

from aiomql import OrderType, Trader, ForexSymbol, Tick, OrderSendResult, VolumeError
from ..utils.ram import RAM
from ..telebots import TelegramBot
from ..utils.sym_utils import calc_loss
logger = getLogger(__name__)


class BaseTrader(Trader):
    risk_to_rewards: list[float]  # risk to reward ratios for multiple trades
    order_updates: list[dict]  # take profit levels for multiple trades
    winning: dict
    losing: dict
    fixed_closer: dict
    open_trades: list[int]

    order_format = "symbol: {symbol}\ntype: {type}\nvolume: {volume}\nsl: {sl}\ntp: {tp}\n" \
                   "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} " \
                   "seconds from now. No reply will be considered as 'cancel'\n" \
                   "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    def __init__(self, *, symbol: ForexSymbol, ram: RAM = None, risk_to_rewards: list[float] = None, multiple=False,
                 use_telegram: bool = True, track_trades: bool = True, use_ram: bool = True, winning: dict = None,
                 losing: dict = None, fixed_closer: dict = None):
        self.data = {}
        ram = ram or RAM(risk_to_reward=3, risk=0.01)
        self.order_updates = []
        self.risk_to_rewards = risk_to_rewards or [1.5, 2, 2.5]
        ram.risk_to_reward = self.risk_to_rewards[-1] if multiple else ram.risk_to_reward
        self.multiple = multiple
        self.use_telegram = use_telegram
        self.track_trades = track_trades
        self.winning = winning or {}
        self.losing = losing or {}
        self.fixed_closer = fixed_closer or {}
        self.open_trades = []
        super().__init__(symbol=symbol, ram=ram)
        ur = getattr(self.config, 'use_ram', False)
        self.use_ram = use_ram if use_ram is not None else ur

    @property
    @cache
    def telebot(self):
        token = getattr(self.config, 'telegram_bot_token', None)
        chat_id = getattr(self.config, 'telegram_chat_id', None)
        confirmation_timeout = getattr(self.config, 'confirmation_timeout', 90)
        return TelegramBot(token=token, chat_id=chat_id, confirmation_timeout=confirmation_timeout,
                           order_format=self.order_format)

    # async def track_history(self):
    #     history =

    def save_trade(self, result: OrderSendResult | list[OrderSendResult]):
        try:
            if not self.track_trades:
                return
            if not self.multiple:
                self.config.state['tracked_trades'][result.order] = result.get_dict(
                    exclude={'retcode_external', 'retcode', 'request_id'}) | {'symbol': self.symbol.name} | self.data
                return

            for res in result:
                self.config.state['tracked_trades'][result.order] = res.get_dict(
                    exclude={'retcode_external', 'retcode', 'request_id'}) | {'symbol': self.symbol.name} | self.data
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.save_trade")

    def save_profit(self, result: OrderSendResult, profit):
        try:
            winning = {'current_profit': profit, 'trail_start': 16, 'trail': 4, 'trailing': False,
                       'extend_start': 0.8, 'start_trailing': True, 'extend_by': 4, 'adjust': 1,
                       'take_profit': 10, 'hedge_trail_start': 10, 'hedge_trail': 3, 'use_trails': True,
                       'trails': {10: 8, 16: 14, 22: 20}, 'last_profit': 0} | self.winning

            losing = {'trail_start': 0.8, 'hedge_point': -10, 'sl_limit': 15, 'trail': 2, 'cut_off': -1,
                      'hedge_cutoff': 0, 'trailing': True, 'last_profit': 0} | self.losing
            fixed_closer = {'close': False, 'cut_off': -1} | self.fixed_closer
            self.config.state['winning'][result.order] = winning
            self.config.state['losing'][result.order] = losing
            self.config.state['fixed_closer'][result.order] = fixed_closer
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.save_profit")

    async def check_ram(self):
        # open_pos = await self.ram.check_open_positions()
        # if open_pos:
        #     raise RuntimeError(f"more than {self.ram.open_limit} open positions present at the same time")

        # bal = await self.ram.check_balance_level()
        # if bal:
        #     raise RuntimeError("Balance level too low")

        # los_pos = await self.ram.check_losing_positions()
        # if los_pos:
        #     raise RuntimeError(f"More than {self.ram.loss_limit} loosing positions present at the same time")
        positions = await self.ram.get_open_positions(symbol=self.symbol.name)
        self.open_trades = [position.ticket for position in positions if position.ticket in self.open_trades]
        if len(self.open_trades) >= self.ram.symbol_limit:
            raise RuntimeError(f"More than {self.ram.symbol_limit} open positions for {self.symbol}"
                               f" present at the same time")
        # pos = await self.ram.check_symbol_positions(symbol=self.symbol.name)
        # if pos:
        #     raise RuntimeError(f"More than {self.ram.open_limit} open positions for {self.symbol}"
        #                        f" present at the same time")

    async def create_order_points(self, order_type: OrderType, points: float = 0, amount: float = 0, **volume_kwargs):
        self.order.type = order_type
        volume, points = await self.symbol.compute_volume_points(amount=amount, points=points, **volume_kwargs)
        self.order.volume = volume
        self.order.comment = self.parameters.get('name', self.__class__.__name__)
        tick = await self.symbol.info_tick()
        if self.multiple:
            self.set_multiple_stop_levels(points=points, tick=tick)
        else:
            self.set_trade_stop_levels(points=points, tick=tick)

    async def create_order_sl(self, order_type: OrderType, sl: float, amount: float, **volume_kwargs):
        tick = await self.symbol.info_tick()
        price = tick.ask if order_type == OrderType.BUY else tick.bid
        volume, sl = await self.symbol.compute_volume_sl(price=price, amount=amount, sl=sl, **volume_kwargs)
        points = abs(sl - price) / self.symbol.point
        self.order.set_attributes(volume=volume, type=order_type,
                                  comment=self.parameters.get('name', self.__class__.__name__))
        if self.multiple:
            self.set_multiple_stop_levels(points=points, tick=tick)
        else:
            self.set_trade_stop_levels(points=points, tick=tick)

    def set_multiple_stop_levels(self, *, points, tick: Tick):
        self.set_trade_stop_levels(points=points, tick=tick)
        points = points * self.symbol.point
        if self.order.type == OrderType.BUY:
            self.order_updates = [{'tp': round(self.order.price + points * rr, self.symbol.digits), 'rr': rr}
                                  for rr in self.risk_to_rewards]
        else:
            self.order_updates = [{'tp': round(self.order.price - points * rr, self.symbol.digits), 'rr': rr}
                                  for rr in self.risk_to_rewards]

    async def notify(self, msg: str = ''):
        try:
            if self.use_telegram and getattr(self.config, 'use_telegram', False):
                self.config.task_queue.add_task(self.telebot.notify, msg=msg)
        except Exception as err:
            logger.error(f"{err} for {self.order.symbol} in {self.__class__.__name__}.notify")

    async def confirm_order(self, *, order: dict = None, order_format: str = '') -> bool:
        try:
            if self.use_telegram and getattr(self.config, 'use_telegram', False):
                order = order or self.order.get_dict(include={'symbol', 'type', 'sl', 'volume', 'tp'})
                ok = await self.telebot.order_confirmation(order=order, order_format=order_format)
                return ok
            else:
                return True
        except Exception as err:
            logger.error(f"{err} for {self.order.symbol} in {self.__class__.__name__}.confirm_order")
            return True

    async def send_order(self) -> OrderSendResult | list[OrderSendResult]:
        if not self.multiple:
            ok = await self.confirm_order()
            if not ok:
                raise RuntimeError("Order not confirmed")
            res = await super().send_order()
            if res.retcode == 10009:
                self.save_trade(res)
                profit = await self.order.calc_profit()
                self.save_profit(res, profit)
                await self.notify(msg=f"Placed Trade for {self.symbol}")
                self.open_trades.append(res.order)
        else:
            res = await self.send_multiple_orders()
            self.save_trade(res)
            name = self.parameters.get('name', self.__class__.__name__)
            await self.notify(msg=f"Placed {len(res)} Trades for {self.symbol} with {name}")
        return res

    async def send_multiple_orders(self) -> list[OrderSendResult]:
        try:
            results = []
            self.parameters['rr'] = self.order_updates[-1]['rr']
            res = await super().send_order()
            if res.retcode == 10009:
                results.append(res)
                profit = await self.order.calc_profit()
                self.save_profit(res, profit)
            for update in self.order_updates[:-1]:
                try:
                    self.parameters['rr'] = update.pop('rr')
                    self.order.set_attributes(**update)
                    res = await super().send_order()
                    if res.retcode == 10009:
                        results.append(res)
                        profit = await self.order.calc_profit()
                        self.save_profit(res, profit)
                except Exception as _:
                    pass
            return results
        except Exception as err:
            logger.error(f"{err} for {self.order.symbol} in {self.__class__.__name__}._send_order")

    async def place_trade(self, *args, **kwargs):
        """Places a trade based on the order_type."""
        raise NotImplementedError
