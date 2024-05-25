from aiomql import Symbol, OrderType, MetaTrader
from logging import getLogger

logger = getLogger(__name__)


def calc_profit(*, sym: Symbol, open_price: float, close_price: float, volume: float, order_type: OrderType):
    try:
        calc = MetaTrader()._order_calc_profit
        profit = calc(order_type, sym.name, volume, open_price, close_price)
        return round(profit, 2)
    except Exception as exe:
        logger.warning(f'{exe} in calc profit')
