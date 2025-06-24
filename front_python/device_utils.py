import requests
from loguru import logger

from front_configs import *


def get_all_devices():
    url = f"{API_CLAUDE35_URL}/devices/all_token_devices"
    logger.debug(f"url: {url}")
    headers = {"User-Agent": "Apifox/1.0.0 (https://apifox.com)"}
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except Exception as e:
        logger.error(f"get_all_devices error: {e}")
        return None


def logout_device(token, user_agent):
    url = f"{API_CLAUDE35_URL}/devices/logout"
    headers = {"Authorization": token, "User-Agent": user_agent}
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except:
        return None


def get_device_type(user_agent):
    ua = user_agent.lower()
    if "iphone" in ua:
        return "iPhone"
    elif "android" in ua:
        return "Android"
    elif "windows" in ua:
        return "Windows"
    elif "macintosh" in ua:
        return "MacOS"
    else:
        return "Other"
