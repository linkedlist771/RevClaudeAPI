
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import asyncio


async def run_background_task(task):
    with ThreadPoolExecutor() as pool:
        await asyncio.get_event_loop().run_in_executor(pool, task)


#  submit a synchronous function to the event loop to make it asynchronous


async def submit_task2event_loop(func, *args, **kwargs):
    running_loop = asyncio.get_running_loop()
    partial_func = partial(func, *args, **kwargs)
    return await running_loop.run_in_executor(executor=None, func=partial_func)
