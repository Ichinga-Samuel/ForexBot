from logging import getLogger
from functools import cache

from aiomql import OrderType, Trader, ForexSymbol, Tick, OrderSendResult, VolumeError
from ..utils.ram import RAM
from ..telebots import TelegramBot
logger = getLogger(__name__)


class BaseTrader(Trader):
    risk_to_rewards: list[float]  # risk to reward ratios for multiple trades
    order_updates: list[dict]  # take profit levels for multiple trades
    trail_profits: dict
    trail_loss: dict
    fixed_closer: dict

    order_format = "symbol: {symbol}\norder_type: {order_type}\npoints: {points}\namount: {amount}\n" \
                   "volume: {volume}\nrisk_to_reward: {risk_to_reward}\nstrategy: {strategy}\n" \
                   "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout} " \
                   "seconds from now. No reply will be considered as 'cancel'\n" \
                   "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    def __init__(self, *, symbol: ForexSymbol, ram: RAM = None, risk_to_rewards: list[float] = None, multiple=False,
                 use_telegram: bool = False, track_trades: bool = True, tracker_key: str = 'trades',
                 use_ram: bool = True, trail_loss: dict = None, trail_profits: dict = None, fixed_closer: dict = None):
        self.data = {}
        ram = ram or RAM(risk_to_reward=3, risk=0.01)
        self.order_updates = []
        self.risk_to_rewards = risk_to_rewards or [1.5, 2, 2.5]
        ram.risk_to_reward = self.risk_to_rewards[-1] if multiple else ram.risk_to_reward
        self.multiple = multiple
        self.use_telegram = use_telegram
        self.track_trades = track_trades
        self.trail_profits = trail_profits or {}
        self.trail_loss = trail_loss or {}
        self.fixed_closer = fixed_closer or {}
        self.tracker_key = tracker_key or self.__class__.__name__
        super().__init__(symbol=symbol, ram=ram)
        ur = getattr(self.config, 'use_ram', False)
        self.use_ram = use_ram if use_ram is not None else ur

    @property
    @cache
    def telebot(self):
        token = self.config.telegram_bot_token
        chat_id = self.config.telegram_chat_id
        confirmation_timeout = self.config.confirmation_timeout
        return TelegramBot(token=token, chat_id=chat_id, confirmation_timeout=confirmation_timeout)

    def save_trade(self, result: OrderSendResult | list[OrderSendResult], key: str = ''):
        try:
            if not self.track_trades:
                return
            key = key or self.tracker_key
            if not self.multiple:
                self.config.state.setdefault(key, {})[result.order] = result.get_dict(
                    exclude={'retcode_external', 'retcode', 'request_id'}) | {'symbol': self.symbol.name} | self.data
                return

            for res in result:
                self.config.state.setdefault(key, {})[res.order] = res.get_dict(
                    exclude={'retcode_external', 'retcode', 'request_id'}) | {'symbol': self.symbol.name} | self.data
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.save_trade")

    def save_profit(self, result: OrderSendResult, profit):
        try:
            winning = {'current_profit': profit, 'trail_start': 9, 'trail': 2, 'trailing': False,
                       'extend_start': 0.8, 'start_trailing': True, 'extend_by': 2,
                       'take_profit': 10, 'hedge_trail_start': 6, 'hedge_trail': 1.5} | self.trail_profits
            losing = {'trail_start': 0.8, 'hedge_point': -3.5, 'sl_limit': 15, 'trail': 0.125, 'cut_off': -1,
                      'hedge_cutoff': 0} | self.trail_loss
            fixed_closer = {'close': False, 'cut_off': -1} | self.fixed_closer
            self.config.state.setdefault('winning', {})[result.order] = winning
            self.config.state.setdefault('losing', {})[result.order] = losing
            self.config.state.setdefault('fixed_closer', {})[result.order] = fixed_closer
        except Exception as err:
            logger.error(f"{err}: for {self.order.symbol} in {self.__class__.__name__}.save_profit")

    async def check_ram(self):
        open_pos = await self.ram.check_open_positions(symbol=self.symbol.name)
        if open_pos:
            raise RuntimeError(f"more than {self.ram.open_limit} open positions present for {self.symbol}")

        bal = await self.ram.check_balance_level()
        if bal:
            raise RuntimeError("Balance level too low")

        pos = await self.ram.check_losing_positions(symbol=self.symbol.name)
        if pos:
            raise RuntimeError(f"More than {self.ram.loss_limit} losing positions")

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
            if self.use_telegram or getattr(self.config, 'use_telegram', False):
                self.config.task_queue.add_task(self.telebot.notify, msg=msg)
        except Exception as err:
            logger.error(f"{err} for {self.order.symbol} in {self.__class__.__name__}.notify")

    async def send_order(self) -> OrderSendResult | list[OrderSendResult]:
        if not self.multiple:
            res = await super().send_order()
            if res.retcode == 10009:
                self.save_trade(res)
                profit = await self.order.calc_profit()
                self.save_profit(res, profit)
                await self.notify(msg=f"Placed Trade for {self.symbol}")
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
