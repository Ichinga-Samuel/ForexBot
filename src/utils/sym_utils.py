from aiomql import Symbol, OrderType


def calc_loss(*, sym: Symbol, open_price: float, close_price: float, volume: float, order_type: OrderType):
    close_price, open_price = (close_price, open_price) if order_type == OrderType.BUY else (open_price, close_price)
    return (close_price - open_price) * sym.trade_contract_size * volume


def calc_profit(*, sym: Symbol, open_price: float, close_price: float, volume: float, order_type: OrderType):
    close_price, open_price = (close_price, open_price) if order_type == OrderType.BUY else (open_price, close_price)
    return (close_price - open_price) * sym.trade_contract_size * volume
