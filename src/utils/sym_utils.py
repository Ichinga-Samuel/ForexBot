from aiomql import Symbol


def calc_profit(sym: Symbol, close_price: float, open_price: float, volume: float):
    return (close_price - open_price) * sym.trade_contract_size * volume
