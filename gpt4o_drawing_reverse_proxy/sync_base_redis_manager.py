# base_redis_manager.py
import json
from datetime import datetime

import pytz
from configs import REDIS_DB, REDIS_HOST, REDIS_PORT
from loguru import logger
from redis import Redis

# Set default timezone to Shanghai
TIMEZONE = pytz.timezone("Asia/Shanghai")


class SyncBaseRedisManager:
    # Class-level cache to store instances
    _instances = {}

    def __new__(cls, host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB):
        """Implement singleton pattern for each unique connection configuration."""
        key = (cls.__name__, host, port, db)
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
        return cls._instances[key]

    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB):
        """Initialize the connection to Redis."""
        # Only initialize if not already initialized
        if not hasattr(self, "host"):
            self.host = host
            self.port = port
            self.db = db
            self.aioredis = None

    def get_aioredis(self):
        if self.aioredis is None:
            self.aioredis = Redis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}", decode_responses=True
            )
        return self.aioredis

    def decoded_get(self, key):
        res = (self.get_aioredis()).get(key)
        if isinstance(res, bytes):
            res = res.decode("utf-8")
        return res

    def get_dict_value_async(self, key):
        value = self.decoded_get(key)
        if value is None:
            return {}
        try:
            res = json.loads(value)
            if not isinstance(res, dict):
                return {}
            else:
                return res
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_async(self, key, value):
        (self.get_aioredis()).set(key, value)

    def exists_async(self, key):
        return (self.get_aioredis()).exists(key)


class FlaskUserRecordManager(SyncBaseRedisManager):
    """
    实现一样的功能， 输入的key是用户的account， 记录以下信息：
    1. 使用次数， 上一次使用时间。
    2. 生成的图片时间， 以及图片的地址
    """

    UPLOADED_FILES_KEY = "shared:uploaded_file_ids"  # 共享的上传文件ID存储键

    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB):
        super().__init__(host, port, db)
        self.redis = self.get_aioredis()

    def get_account_key(self, account):
        return f"account:{account}"

    """
    设置的变量值为:
    gfsessionids: 一个列表， 记录了所有绑定到该account的gfsessionid
    chat_usage_count: 一个整数， 记录了该account的使用次数
    last_used: 一个字符串， 记录了该account上一次使用的时间
    images: 一个列表， 记录了该account生成的图片信息， 每个图片信息是一个字典， 字典中包含图片的地址， 以及图片的生成时间
    """

    def bind_gfsessionid_to_account(self, account, gfsessionid):
        """Bind a gfsessionid to an account"""
        try:
            account_key = self.get_account_key(account)
            user_data = self.get_dict_value_async(account_key)
            current_time = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

            # Initialize gfsessionids list if it doesn't exist
            if "gfsessionids" not in user_data:
                user_data["gfsessionids"] = []

            # Add new gfsessionid if not already in the list
            if gfsessionid not in user_data["gfsessionids"]:
                user_data["gfsessionids"].append(gfsessionid)

            # Initialize images list if it doesn't exist
            if "images" not in user_data:
                user_data["images"] = []

            user_data.update(
                {
                    "last_used": current_time,
                    "chat_usage_count": user_data.get("chat_usage_count", 0),
                }
            )

            self.set_async(account_key, json.dumps(user_data))
            logger.debug(f"Successfully bound gfsessionid to account: {account}")
            return True
        except Exception as e:
            logger.error(f"Error binding gfsessionid to account: {str(e)}")
            return False

    def update_usage_for_gfsessionid(self, gfsessionid):
        """Update usage count for an account based on gfsessionid"""
        try:
            # Find account by gfsessionid
            for raw_key in self.redis.keys("account:*"):
                account_key = raw_key
                user_data = self.get_dict_value_async(account_key)
                # Check both the backward compatibility field and the new list
                gfsessionids = user_data.get("gfsessionids", [])
                if gfsessionid in gfsessionids:
                    current_time = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
                    user_data.update(
                        {
                            "chat_usage_count": user_data.get("chat_usage_count", 0)
                            + 1,
                            "last_used": current_time,
                        }
                    )
                    self.set_async(account_key, json.dumps(user_data))
                    logger.debug(f"Updated usage count for account: {account_key}")
                    return True
            logger.warning(f"No account found for gfsessionid: {gfsessionid}")
            return False
        except Exception as e:
            logger.error(f"Error updating usage count: {str(e)}")
            return False

    def add_image_to_account(self, account, image_url):
        """Add a generated image to an account's history"""
        try:
            account_key = self.get_account_key(account)
            user_data = self.get_dict_value_async(account_key)
            current_time = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

            # Initialize images list if it doesn't exist
            if "images" not in user_data:
                user_data["images"] = []

            # Add new image info
            image_info = {"url": image_url, "generated_at": current_time}
            user_data["images"].append(image_info)

            self.set_async(account_key, json.dumps(user_data))
            logger.debug(f"Added image to account: {account}")
            return True
        except Exception as e:
            logger.error(f"Error adding image to account: {str(e)}")
            return False

    def add_image_to_account_by_gfsessionid(self, gfsessionid, image_url):
        """Get account information by gfsessionid"""
        try:
            for raw_key in self.redis.keys("account:*"):
                account_key = raw_key
                user_data = self.get_dict_value_async(account_key)

                # Check both the backward compatibility field and the new list
                gfsessionids = user_data.get("gfsessionids", [])
                if gfsessionid in gfsessionids:
                    self.add_image_to_account(
                        account_key.removeprefix("account:"), image_url
                    )
                    return user_data
            return None
        except Exception as e:
            logger.error(f"Error getting account by gfsessionid: {str(e)}")
            return None

    def get_account_by_gfsessionid(self, gfsessionid):
        """Get account information by gfsessionid"""
        try:
            for raw_key in self.redis.keys("account:*"):
                account_key = raw_key
                user_data = self.get_dict_value_async(account_key)

                # Check both the backward compatibility field and the new list
                gfsessionids = user_data.get("gfsessionids", [])
                if gfsessionid in gfsessionids:
                    return user_data
            return None
        except Exception as e:
            logger.error(f"Error getting account by gfsessionid: {str(e)}")
            return None

    def get_usage_stats(self, account=None, limit=-1, page=1, page_size=10):
        """Get usage statistics for an account or all accounts

        Args:
            account (str, optional): Specific account to get stats for. Defaults to None.
            limit (int, optional): Limit on number of accounts to return. Defaults to -1.
            page (int, optional): Page number for images pagination. Defaults to 1.
            page_size (int, optional): Number of images per page. Defaults to 10.
        """
        try:
            if account:
                account_key = self.get_account_key(account)
                user_data = self.get_dict_value_async(account_key)
                if user_data:
                    # Sort images by generated_at in descending order
                    if "images" in user_data:
                        images = sorted(
                            user_data["images"],
                            key=lambda x: x.get("generated_at", ""),
                            reverse=True,
                        )
                        # Calculate pagination
                        start_idx = (page - 1) * page_size
                        end_idx = start_idx + page_size
                        user_data["images"] = images[start_idx:end_idx]
                        user_data["total_images"] = len(images)
                        user_data["current_page"] = page
                        user_data["total_pages"] = (
                            len(images) + page_size - 1
                        ) // page_size
                    return user_data
                return {"message": f"No data found for account: {account}"}
            else:
                stats = []
                for raw_key in self.redis.keys("account:*")[:limit]:
                    user_data = self.get_dict_value_async(raw_key)
                    if user_data:
                        # Sort and paginate images for each account
                        if "images" in user_data:
                            images = sorted(
                                user_data["images"],
                                key=lambda x: x.get("generated_at", ""),
                                reverse=True,
                            )
                            start_idx = (page - 1) * page_size
                            end_idx = start_idx + page_size
                            user_data["images"] = images[start_idx:end_idx]
                            user_data["total_images"] = len(images)
                            user_data["current_page"] = page
                            user_data["total_pages"] = (
                                len(images) + page_size - 1
                            ) // page_size
                        stats.append(user_data)
                return stats
        except Exception as e:
            logger.error(f"Error getting usage stats: {str(e)}")
            return []

    def get_account_images(self, account, limit=None):
        """Get images generated by an account"""
        try:
            account_key = self.get_account_key(account)
            user_data = self.get_dict_value_async(account_key)
            if not user_data or "images" not in user_data:
                return []

            images = user_data["images"]
            if limit and isinstance(limit, int):
                return images[-limit:]  # Return most recent images
            return images
        except Exception as e:
            logger.error(f"Error getting account images: {str(e)}")
            return []

    def add_uploaded_file_id(self, file_id):
        """Add a file_id to the shared uploaded files set"""
        try:
            uploaded_files = self.get_dict_value_async(self.UPLOADED_FILES_KEY)
            if not uploaded_files:
                uploaded_files = {"file_ids": []}

            if file_id not in uploaded_files["file_ids"]:
                uploaded_files["file_ids"].append(file_id)
                self.set_async(self.UPLOADED_FILES_KEY, json.dumps(uploaded_files))
                logger.debug(f"Added file_id {file_id} to shared uploaded files")
            return True
        except Exception as e:
            logger.error(f"Error adding file_id to shared uploaded files: {str(e)}")
            return False

    def is_uploaded_file(self, file_id):
        """Check if a file_id exists in the shared uploaded files set"""
        try:
            uploaded_files = self.get_dict_value_async(self.UPLOADED_FILES_KEY)
            return uploaded_files and file_id in uploaded_files.get("file_ids", [])
        except Exception as e:
            logger.error(f"Error checking uploaded file_id: {str(e)}")
            return False
