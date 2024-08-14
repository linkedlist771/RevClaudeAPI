import os
import time
from loguru import logger
from datetime import datetime
import pytz


def set_cn_time_zone():
    """设置当前进程的时区为中国时区"""
    os.environ["TZ"] = "Asia/Shanghai"
    try:
        time.tzset()
        logger.info("Set time zone to Asia/Shanghai.")
    except Exception as e:
        logger.error(f"Failed to set time zone: {e}")


def get_shanghai_time():
    # 获取当前UTC时间，然后转换为上海时间
    shanghai_tz = pytz.timezone("Asia/Shanghai")

    return datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(shanghai_tz)
