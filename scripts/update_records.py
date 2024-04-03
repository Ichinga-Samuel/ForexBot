import asyncio
from aiomql import Records, Account, Config


async def update_records():
    """Update all records"""
    async with Account() as acc:
        rec = Records()
        await rec.update_records()


if __name__ == "__main__":
    Config(config_dir='configs', filename='deriv_demo.json', reload=True, records_dir='records/deriv1/', root_dir='../')
    asyncio.run(update_records())
