import asyncio
from pathlib import Path

from aiomql import Records, Account


async def update_records(login: int = 0, password: str = None, server: str = None, folder: Path = ''):
    """Update all records"""
    async with Account(login=login, password=password, server=server) as _:
        rec = Records(records_dir=folder)
        await rec.update_records()


asyncio.run(update_records(login=42462935, server="Aglobe-Demo", password="6C#vtAkC49ln9+", folder=Path.home() / 'Documents' / 'Aiomql' / 'Admirals'))