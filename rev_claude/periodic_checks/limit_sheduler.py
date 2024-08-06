from datetime import datetime

from rev_claude.periodic_checks.clients_limit_checks import check_reverse_official_usage_limits
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

limit_check_scheduler = AsyncIOScheduler()

# 设置定时任务
limit_check_scheduler.add_job(
    check_reverse_official_usage_limits,
    trigger=IntervalTrigger(minutes=10),
    id='check_usage_limits',
    name='Check API usage limits every 10 minutes',
    replace_existing=True,
    next_run_time=datetime.now()  # 这会使任务立即运行一次
)


