from guardrails import AsyncGuard
import asyncio
import inspect

async def check():
    g = AsyncGuard()
    print(f"AsyncGuard.validate is async: {inspect.iscoroutinefunction(g.validate)}")

asyncio.run(check())
