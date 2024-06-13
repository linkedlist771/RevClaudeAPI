import os
import time
from loguru import logger


def set_cn_time_zone():
    """设置当前进程的时区为中国时区"""
    os.environ['TZ'] = 'Asia/Shanghai'
    time.tzset()
    logger.info("Set time zone to Asia/Shanghai.")