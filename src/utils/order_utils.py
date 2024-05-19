from aiomql import Symbol, OrderType
from logging import getLogger

logger = getLogger(__name__)


def calc_loss(*, sym: Symbol, open_price: float, close_price: float, volume: float, order_type: OrderType):
    try:
        close_price, open_price = (close_price, open_price) if order_type == OrderType.BUY else (open_price, close_price)
        return round((close_price - open_price) * sym.trade_contract_size * volume, 2)
    except Exception as exe:
        logger.warning(f'{exe} in calc loss')


def calc_profit(*, sym: Symbol, open_price: float, close_price: float, volume: float, order_type: OrderType):
    close_price, open_price = (close_price, open_price) if order_type == OrderType.BUY else (open_price, close_price)
    return round((close_price - open_price) * sym.trade_contract_size * volume, 2)
