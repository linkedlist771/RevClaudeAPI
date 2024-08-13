import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from rev_claude.configs import CLAUDE_CLIENT_LIMIT_CHECKS_INTERVAL_MINUTES
from rev_claude.periodic_checks.clients_limit_checks import (
    check_reverse_official_usage_limits,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# limit_check_scheduler = AsyncIOScheduler()
#
# limit_check_scheduler.add_job(
#     check_reverse_official_usage_limits,
#     trigger=IntervalTrigger(minutes=CLAUDE_CLIENT_LIMIT_CHECKS_INTERVAL_MINUTES),
#     id="check_usage_limits",
#     name=f"Check API usage limits every {CLAUDE_CLIENT_LIMIT_CHECKS_INTERVAL_MINUTES} minutes",
#     replace_existing=True,
# )


def run_scheduler():
    async def async_run():
        limit_check_scheduler = AsyncIOScheduler()
        limit_check_scheduler.add_job(
            check_reverse_official_usage_limits,
            trigger=IntervalTrigger(minutes=CLAUDE_CLIENT_LIMIT_CHECKS_INTERVAL_MINUTES),
            id="check_usage_limits",
            name=f"Check API usage limits every {CLAUDE_CLIENT_LIMIT_CHECKS_INTERVAL_MINUTES} minutes",
            replace_existing=True,
        )
        limit_check_scheduler.start()

        try:
            # Keep the process running
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            limit_check_scheduler.shutdown()

    asyncio.run(async_run())


#

# class LimitScheduler:
#     limit_check_scheduler = limit_check_scheduler
#
#     @staticmethod
#     async def start():
#         # await check_reverse_official_usage_limits()
#         limit_check_scheduler.start()
#
#     @staticmethod
#     async def shutdown():
#         limit_check_scheduler.shutdown()


class LimitScheduler:
    process = None
    pool = None

    @staticmethod
    async def start():
        LimitScheduler.pool = ProcessPoolExecutor(max_workers=1)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(LimitScheduler.pool, run_scheduler)

    @staticmethod
    async def shutdown():
        if LimitScheduler.pool:
            LimitScheduler.pool.shutdown(wait=True)
