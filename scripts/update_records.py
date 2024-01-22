import asyncio
from aiomql import Records, Account


async def update_records():
    """Update all records"""
    async with Account() as _:
        rec = Records()
        await rec.update_records()


asyncio.run(update_records())