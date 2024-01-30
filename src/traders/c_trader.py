from logging import getLogger

from aiomql import OrderType

from .base_trader import BaseTrader

logger = getLogger(__name__)


class CTrader(BaseTrader):
    """Points Based Trader"""
    async def create_order(self, *, order_type: OrderType, acl: float):
        amount = await self.ram.get_amount()
        tick = await self.symbol.info_tick()
        sl = tick.ask - acl if order_type == OrderType.BUY else tick.bid + acl
        tp = tick.ask + (acl * self.ram.risk_to_reward) if order_type == OrderType.BUY else tick.bid - (acl * self.ram.risk_to_reward)
        points = self.symbol.trade_stops_level + (self.symbol.spread * 1.5)
        v_points = (tick.ask - sl) / self.symbol.point if order_type == OrderType.BUY else abs(sl - tick.bid) / self.symbol.point
        if v_points >= points:
            self.track_trades = False
            return await self.create_order_points(order_type=order_type, points=v_points, amount=amount)

        self.track_trades = True
        self.tracker_key = 'c_trader'
        self.data = {'close_sl': sl, 'close_tp': tp}
        v_amount = self.symbol.volume_min * self.symbol.point * v_points * self.symbol.trade_contract_size
        volume = (amount * self.symbol.volume_min) / v_amount
        self.order.set_attributes(type=order_type, volume=self.symbol.round_off_volume(volume))
        self.set_trade_stop_levels(points=points, tick=tick)

    async def place_trade(self, *, order_type: OrderType, acl: float, parameters: dict = None):
        try:
            self.parameters |= parameters or {}
            await self.create_order(order_type=order_type, acl=acl)
            if not await self.check_order():
                return
            await self.send_order()
        except Exception as err:
            logger.error(f"{err}. Symbol: {self.order.symbol}\n {self.__class__.__name__}.place_trade")