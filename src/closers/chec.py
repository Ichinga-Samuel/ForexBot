import asyncio


async def fun():
    await asyncio.sleep(1)
    return 'fun1'


async def fun2():
    await asyncio.sleep(1)
    raise ValueError('f')


async def main():
    a, b = await asyncio.gather(fun(), fun2(), return_exceptions=True)
    print(a, isinstance(b, Exception))
asyncio.run(main())
