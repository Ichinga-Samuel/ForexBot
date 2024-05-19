import asyncio
from logging import getLogger
import random

from telegram import Bot

logger = getLogger(__name__)

all_updates = list()


class TelegramBot:
    def __init__(self, *, token=None, confirmation_timeout=60, chat_id=0, order_format=''):
        self.bot = Bot(token)
        self.confirmation_timeout = confirmation_timeout
        self.chat_id = chat_id
        self.order_format = order_format or "symbol: {symbol}\norder_type: {order_type}\npips: {pips}\n" \
                                            "volume: {volume}\nrisk_to_reward: {risk_to_reward}\n" \
                                            "hint: reply with 'ok' to confirm or 'cancel' to cancel in {timeout}" \
                                            "seconds from now. No reply will be considered as 'cancel'\n" \
                                            "NB: For order_type; 0 = 'buy' and 1 = 'sell' see docs for more info"

    @staticmethod
    def extract_order(msg: str, trade_order: dict) -> dict:
        try:
            order = msg.split('\n')
            order = {key: v.strip(' ') for r in order for k, v in [r.split(':')] if (key := k.strip(' ')) in trade_order}
            for key in order:
                if key in ('pips', 'volume', 'risk_to_reward', 'order_type', 'amount', 'points'):
                    trade_order[key] = float(order[key]) if key != 'order_type' else int(order[key])
            return trade_order
        except Exception as exe:
            raise RuntimeError(f'Could not extract order from your response: {msg} due to {exe}')

    async def get_updates(self, tries=3):
        if tries == 0:
            await asyncio.sleep(random.random())
            return await self.bot.get_updates()

        ups = await self.bot.get_updates()
        if len(ups) == 1:
            await asyncio.sleep(random.random())
            return await self.get_updates(tries=tries-1)
        return ups

    async def notify(self, msg):
        await self.bot.send_message(chat_id=self.chat_id, text=msg)

    async def confirm_order(self, *, order: dict):
        order_msg = self.order_format.format(timeout=self.confirmation_timeout, **order)
        msg = await self.bot.send_message(chat_id=self.chat_id, text=order_msg)
        msg_id = msg.message_id
        reply = 'cancel'
        await asyncio.sleep(self.confirmation_timeout)
        updates = await self.get_updates()
        for update in updates[::-1]:
            if reply_to_message := getattr(update.message, 'reply_to_message'):
                if msg_id == reply_to_message.message_id:
                    reply = update.message.text
                    break
        if reply.lower() == 'ok':
            return order

        if reply.lower() == 'cancel':
            raise RuntimeError('Order cancelled')

        return self.extract_order(reply, order)

    async def get_order_confirmation(self, *, order: dict, order_format: str = '', tries=3) -> bool:
        try:
            order_format = order_format or self.order_format
            order_msg = order_format.format(timeout=self.confirmation_timeout, **order)
            reply = 'cancel'
            while tries > 0:
                msg = await self.bot.send_message(chat_id=self.chat_id, text=order_msg)
                msg_id = msg.message_id
                await asyncio.sleep(self.confirmation_timeout)
                updates = await self.get_updates()
                for update in updates[::-1]:
                    if reply_to_message := getattr(update.message, 'reply_to_message'):
                        if msg_id == reply_to_message.message_id:
                            reply = update.message.text
                            break
                if reply.lower() == 'ok':
                    return True
                else:
                    tries -= 1

            if reply.lower() == 'cancel':
                return False
        except Exception as exe:
            logger.error(f"Could not confirm order due to {exe}")
            return False
