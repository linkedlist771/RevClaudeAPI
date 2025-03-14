import json
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import List

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

        Args:
            renewal_code: The renewal code to use
            api_key: The API key to extend

        Returns:
            str: Success/error message
        """
        # 1. First get the renewal code info
        code_info = await self.get_renewal_code(renewal_code)
        if not code_info:
            return "无效的续费码"

        # 2. Check if it's already used
        if code_info.status == RenewalKeyStatus.USED:
            return "该续费码已被使用"

        # 3. Mark it as used BEFORE processing the renewal
        # This helps prevent race conditions
        await self.mark_as_used(renewal_code, api_key)

        # 4. Process the renewal
        total_minutes = code_info.total_minutes()

        if total_minutes <= 0:
            return "续费码无效：续期时间必须大于0"

        # Convert minutes to days for the API key manager
        days = total_minutes / (24 * 60)
        result = await renew_api_key(api_key, days)

        return f"成功续期 {code_info.days} 天 {code_info.hours} 小时 "

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
