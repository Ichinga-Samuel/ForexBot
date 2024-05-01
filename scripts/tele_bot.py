import asyncio
from src.telebots import TelegramBot


async def test_bot():
    bot = TelegramBot(token="6645070821:AAGgdWAgnzO9jbS4_fRUFtByG4hMJM9woSM", chat_id="-1002091189701")
    await bot.notify('testing')


asyncio.run(test_bot())
