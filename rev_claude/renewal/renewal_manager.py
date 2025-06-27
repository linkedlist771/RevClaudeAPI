import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import List

from loguru import logger
from pydantic import BaseModel

from rev_claude.redis_manager.base_redis_manager import BaseRedisManager
from rev_claude.renewal.utils import renew_api_key


class RenewalKeyStatus(Enum):
    UNUSED = "unused"
    USED = "used"


class RenewalCode(BaseModel):
    code: str
    status: RenewalKeyStatus
    days: int
    hours: int
    minutes: int
    created_at: datetime
    used_at: datetime | None = None
    used_by: str | None = None

    def total_minutes(self) -> int:
        """Get total minutes from days, hours and minutes"""
        return self.days * 24 * 60 + self.hours * 60 + self.minutes

    def to_json(self) -> str:
        """Convert to JSON string with proper datetime and enum handling"""
        data = self.model_dump()
        # Convert datetime objects to ISO format strings
        data["created_at"] = self.created_at.isoformat()
        data["used_at"] = self.used_at.isoformat() if self.used_at else None
        # Convert enum to string
        data["status"] = self.status.value  # Convert enum to string
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "RenewalCode":
        """Create RenewalCode instance from JSON string"""
        data = json.loads(json_str)
        # Convert ISO format strings back to datetime objects
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data["used_at"]:
            data["used_at"] = datetime.fromisoformat(data["used_at"])
        # Convert string back to enum
        data["status"] = RenewalKeyStatus(data["status"])
        return cls(**data)


class RenewalManager(BaseRedisManager):
    def _get_renewal_key(self, renewal_code: str) -> str:
        """Get the Redis key for storing renewal code information."""
        return f"renewal:{renewal_code}"

    async def create_renewal_code(
        self, days: int = 0, hours: int = 0, minutes: int = 0, count: int = 1
    ) -> List[str]:
        """
        Create one or more renewal codes that can be used to extend an API key's expiration.
        Format: rnw-{days}_{hours}_{minutes}-{date}-{random}

        Args:
            days: Number of days to extend
            hours: Number of hours to extend
            minutes: Number of minutes to extend
            count: Number of renewal codes to generate (default: 1)

        Returns:
            List[str]: List of generated renewal codes
        """
        if days == 0 and hours == 0 and minutes == 0:
            raise ValueError("Total duration must be greater than 0")
        if count < 1:
            raise ValueError("Count must be at least 1")

        # Normalize the time values (convert excess minutes to hours, excess hours to days)
        additional_hours, final_minutes = divmod(minutes, 60)
        hours += additional_hours
        additional_days, final_hours = divmod(hours, 24)
        final_days = days + additional_days

        # Generate date part
        current_time = datetime.now()
        date_str = current_time.strftime("%m%d")  # MMDD format

        codes = []
        for _ in range(count):
            # Generate random part
            random_str = str(uuid.uuid4())[:6]

            # Create code with time information
            code = f"rnw-{final_days}_{final_hours}_{final_minutes}-{date_str}-{random_str}"

            renewal_code = RenewalCode(
                code=code,
                status=RenewalKeyStatus.UNUSED,
                days=final_days,
                hours=final_hours,
                minutes=final_minutes,
                created_at=current_time,
            )

            await self.set_async(self._get_renewal_key(code), renewal_code.to_json())

            codes.append(code)

        return codes

    async def get_renewal_code(self, code: str) -> RenewalCode | None:
        """Get renewal code information"""
        data = await self.decoded_get(self._get_renewal_key(code))
        if not data:
            return None
        return RenewalCode.from_json(data)

    async def is_valid_renewal_code(self, code: str) -> bool:
        """Check if a renewal code exists and is unused."""
        renewal_code = await self.get_renewal_code(code)
        if not renewal_code:
            return False
        return renewal_code.status == RenewalKeyStatus.UNUSED

    async def mark_as_used(self, code: str, api_key: str):
        """Mark a renewal code as used."""
        renewal_code = await self.get_renewal_code(code)
        if renewal_code:
            renewal_code.status = RenewalKeyStatus.USED
            renewal_code.used_at = datetime.now()
            renewal_code.used_by = api_key
            await self.set_async(self._get_renewal_key(code), renewal_code.to_json())

    async def use_renewal_code(self, renewal_code: str, api_key: str) -> str:
        """
        Use a renewal code to extend an API key's expiration.
        Includes retry mechanism and async verification to ensure successful renewal.

        Args:
            renewal_code: The renewal code to use
            api_key: The API key to extend

        Returns:
            str: Success/error message
        """
        import asyncio
        from rev_claude.renewal.utils import get_api_key_information
        
        logger.info(f"开始使用续费码 {renewal_code} 为 API Key {api_key[:8]}*** 进行续费")
        
        # 1. First get the renewal code info
        code_info = await self.get_renewal_code(renewal_code)
        if not code_info:
            logger.error(f"续费码 {renewal_code} 不存在")
            return "无效的续费码"

        # 2. Check if it's already used
        if code_info.status == RenewalKeyStatus.USED:
            logger.warning(f"续费码 {renewal_code} 已被使用")
            return "该续费码已被使用"

        # 3. Validate renewal parameters
        total_minutes = code_info.total_minutes()
        if total_minutes <= 0:
            logger.error(f"续费码 {renewal_code} 无效：续期时间必须大于0")
            return "续费码无效：续期时间必须大于0"

        # 4. Get current API key info for comparison later
        logger.info(f"获取 API Key {api_key[:8]}*** 当前信息用于续费前后对比")
        original_api_info = await get_api_key_information(api_key)
        if not original_api_info:
            logger.error(f"API Key {api_key[:8]}*** 不存在")
            return "API Key 不存在"
        
        original_expire_time = original_api_info.get("expireTime")
        logger.info(f"API Key {api_key[:8]}*** 原始过期时间: {original_expire_time}")

        # 5. Convert minutes to days for the API key manager
        days = total_minutes / (24 * 60)
        logger.info(f"准备为 API Key {api_key[:8]}*** 续费 {days:.2f} 天 ({code_info.days}天{code_info.hours}小时{code_info.minutes}分钟)")

        # 6. Retry mechanism for renewal
        max_retries = 3
        retry_count = 0
        renewal_result = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"执行续费操作 - 第 {retry_count + 1} 次尝试 (共 {max_retries} 次)")
                renewal_result = await renew_api_key(api_key, days)
                logger.info(f"续费请求执行完成 - 第 {retry_count + 1} 次尝试，结果: {renewal_result}")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"续费请求失败 - 第 {retry_count} 次尝试，错误: {str(e)}")
                if retry_count < max_retries:
                    logger.info(f"等待 1 秒后进行第 {retry_count + 1} 次重试")
                    await asyncio.sleep(1)  # 减少等待时间为1秒
                else:
                    logger.error(f"续费请求在 {max_retries} 次尝试后全部失败")
                    return f"续费请求失败，已重试 {max_retries} 次"

        # 7. 立即标记续费码为已使用（后续验证失败会回滚）
        await self.mark_as_used(renewal_code, api_key)
        logger.info(f"续费码 {renewal_code} 已标记为已使用")

        # 8. 创建异步验证任务，不阻塞返回
        verification_task = asyncio.create_task(
            self._async_verify_renewal(
                renewal_code, api_key, original_api_info, days, code_info
            )
        )
        logger.info(f"已创建异步验证任务，任务ID: {id(verification_task)}")

        # 9. 立即返回成功消息
        logger.info(f"续费操作已提交完成，正在后台验证。API Key {api_key[:8]}*** 续费 {days:.2f} 天")
        return f"续费操作已提交，正在后台验证续期 {code_info.days} 天 {code_info.hours} 小时 {code_info.minutes} 分钟"

    async def _rollback_renewal_code(self, renewal_code: str):
        """回滚续费码状态为未使用"""
        try:
            code_info = await self.get_renewal_code(renewal_code)
            if code_info:
                code_info.status = RenewalKeyStatus.UNUSED
                code_info.used_at = None
                code_info.used_by = None
                await self.set_async(self._get_renewal_key(renewal_code), code_info.to_json())
                logger.info(f"续费码 {renewal_code} 状态已回滚为未使用")
        except Exception as e:
            logger.error(f"回滚续费码 {renewal_code} 状态失败: {str(e)}")

    async def _async_verify_renewal(self, renewal_code: str, api_key: str, original_api_info: dict, expected_days: float, code_info):
        """
        异步验证续费是否成功，如果失败则尝试重新续费，最终失败才回滚续费码状态
        """
        import asyncio
        from rev_claude.renewal.utils import get_api_key_information, renew_api_key
        
        logger.info(f"开始异步验证任务 - 续费码: {renewal_code}, API Key: {api_key[:8]}***")
        
        try:
            # 第一次验证：等待15秒
            logger.info("等待 15 秒后进行第一次验证")
            await asyncio.sleep(15)
            
            logger.info(f"开始第一次验证 API Key {api_key[:8]}*** 续费是否生效")
            updated_api_info = await get_api_key_information(api_key)
            
            if updated_api_info and self._verify_renewal_success(original_api_info, updated_api_info, expected_days):
                logger.info(f"第一次验证成功：API Key {api_key[:8]}*** 续费已生效")
                return
            
            # 第一次验证失败，尝试重新续费
            logger.warning("第一次验证失败，尝试第一次重新续费")
            try:
                first_retry_result = await renew_api_key(api_key, expected_days)
                logger.info(f"第一次重新续费请求执行完成，结果: {first_retry_result}")
                
                # 等待30秒后验证
                logger.info("第一次重新续费后等待 30 秒进行验证")
                await asyncio.sleep(30)
                
                verification_api_info = await get_api_key_information(api_key)
                if verification_api_info and self._verify_renewal_success(original_api_info, verification_api_info, expected_days):
                    logger.info(f"第一次重新续费后验证成功：API Key {api_key[:8]}*** 续费已生效")
                    return
                    
            except Exception as e:
                logger.error(f"第一次重新续费操作失败: {str(e)}")
            
            # 第二次验证：等待1分钟
            logger.warning("第一次重新续费未成功，等待 1 分钟后进行第二次验证")
            await asyncio.sleep(60)
            
            logger.info(f"开始第二次验证 API Key {api_key[:8]}*** 续费是否生效")
            updated_api_info = await get_api_key_information(api_key)
            
            if updated_api_info and self._verify_renewal_success(original_api_info, updated_api_info, expected_days):
                logger.info(f"第二次验证成功：API Key {api_key[:8]}*** 续费已生效")
                return
            
            # 第二次验证失败，尝试第二次重新续费
            logger.warning("第二次验证失败，尝试第二次重新续费")
            try:
                second_retry_result = await renew_api_key(api_key, expected_days)
                logger.info(f"第二次重新续费请求执行完成，结果: {second_retry_result}")
                
                # 等待30秒后最终验证
                logger.info("第二次重新续费后等待 30 秒进行最终验证")
                await asyncio.sleep(30)
                
                final_api_info = await get_api_key_information(api_key)
                if final_api_info and self._verify_renewal_success(original_api_info, final_api_info, expected_days):
                    logger.info(f"第二次重新续费后验证成功：API Key {api_key[:8]}*** 续费已生效")
                    return
                else:
                    logger.error(f"第二次重新续费后验证失败：API Key {api_key[:8]}*** 续费未生效，开始回滚续费码")
                    await self._rollback_renewal_code(renewal_code)
                    
            except Exception as e:
                logger.error(f"第二次重新续费操作失败: {str(e)}，开始回滚续费码")
                await self._rollback_renewal_code(renewal_code)
                
        except Exception as e:
            logger.error(f"异步验证过程发生异常: {str(e)}，开始回滚续费码")
            await self._rollback_renewal_code(renewal_code)

    def _verify_renewal_success(self, original_info: dict, updated_info: dict | None, expected_days: float) -> bool:
        """
        Verify if the renewal was successful by comparing expiration times
        
        Args:
            original_info: Original API key information
            updated_info: Updated API key information after renewal
            expected_days: Expected number of days added
            
        Returns:
            bool: True if renewal was successful, False otherwise
        """
        if not updated_info:
            logger.error("无法获取更新后的 API Key 信息")
            return False
            
        original_expire = original_info.get("expireTime")
        updated_expire = updated_info.get("expireTime")
        
        if not original_expire or not updated_expire:
            logger.error(f"过期时间信息不完整 - 原始: {original_expire}, 更新后: {updated_expire}")
            return False
        
        logger.info(f"验证续费结果 - 原始过期时间: {original_expire}, 更新后过期时间: {updated_expire}")
        
        try:
            from datetime import datetime
            original_dt = datetime.strptime(original_expire, "%Y-%m-%d %H:%M:%S")
            updated_dt = datetime.strptime(updated_expire, "%Y-%m-%d %H:%M:%S")
            
            # Calculate the actual extension in days
            time_diff = updated_dt - original_dt
            actual_days = time_diff.total_seconds() / (24 * 3600)
            
            logger.info(f"实际续费天数: {actual_days:.2f}, 预期续费天数: {expected_days:.2f}")
            
            # Allow for small discrepancies (± 0.1 days = ± 2.4 hours)
            if abs(actual_days - expected_days) <= 0.1:
                logger.info("续费验证成功：实际续费时间与预期匹配")
                return True
            else:
                logger.warning(f"续费验证失败：实际续费天数 {actual_days:.2f} 与预期 {expected_days:.2f} 不匹配")
                return False
                
        except Exception as e:
            logger.error(f"验证续费结果时发生错误: {str(e)}")
            return False

    async def get_renewal_code_info(self, code: str) -> dict:
        """Get detailed information about a renewal code"""
        renewal_code = await self.get_renewal_code(code)
        if not renewal_code:
            return {"error": "续费码不存在"}

        return {
            "code": renewal_code.code,
            "status": renewal_code.status.value,
            "days": renewal_code.days,
            "hours": renewal_code.hours,
            "minutes": renewal_code.minutes,
            "total_minutes": renewal_code.total_minutes(),
            "created_at": renewal_code.created_at.isoformat(),
            "used_at": (
                renewal_code.used_at.isoformat() if renewal_code.used_at else None
            ),
            "used_by": renewal_code.used_by,
        }

    async def get_all_renewal_codes(self) -> List[dict]:
        """Get information about all renewal codes"""
        # Get all keys matching the renewal pattern
        redis = await self.get_aioredis()
        keys = await redis.keys("renewal:*")
        codes = []

        for key in keys:
            data = await self.decoded_get(key)
            if data:
                renewal_code = RenewalCode.from_json(data)
                codes.append(
                    {
                        "code": renewal_code.code,
                        "status": renewal_code.status.value,
                        "days": renewal_code.days,
                        "hours": renewal_code.hours,
                        "minutes": renewal_code.minutes,
                        "total_minutes": renewal_code.total_minutes(),
                        "created_at": renewal_code.created_at.isoformat(),
                        "used_at": (
                            renewal_code.used_at.isoformat()
                            if renewal_code.used_at
                            else None
                        ),
                        "used_by": renewal_code.used_by,
                    }
                )

        # Sort by created_at, most recent first
        codes.sort(key=lambda x: x["created_at"], reverse=True)
        return codes

    async def delete_renewal_codes(self, codes: List[str] | str) -> dict:
        """
        Delete one or multiple renewal codes

        Args:
            codes: Single renewal code string or list of renewal codes

        Returns:
            dict: Results of deletion operation
        """
        if isinstance(codes, str):
            codes = [codes]

        results = {"success": [], "not_found": []}

        redis = await self.get_aioredis()
        for code in codes:
            key = self._get_renewal_key(code)
            exists = await redis.exists(key)
            if exists:
                await redis.delete(key)
                results["success"].append(code)
            else:
                results["not_found"].append(code)

        return results
