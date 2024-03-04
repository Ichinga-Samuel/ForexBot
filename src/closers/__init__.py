from .closer import closer, OpenTrade
from .ema_rsi_closer import ema_rsi_closer
from .ema_closer import ema_closer
from .points_closer import close_at_sl
from .st_closer import close_by_stoch
from .trailing_stop import trailing_stop
from .hedge import hedge
from .alt_hedge import hedge as alt_hedge
from .trailing_stops import trailing_stops
from .catch_up import linkups
from .trailing_loss import trail_sl
from .fixed_closer import fixed_closer
# TODO: use trailing stop in the closers if the trade is in profit
