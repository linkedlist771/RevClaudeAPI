from rev_claude.redis_manager.base_redis_manager import BaseRedisManager
import uuid
from enum import Enum
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
from typing import List


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
        """Convert to JSON string with proper datetime handling"""
        data = self.model_dump()
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        data['used_at'] = self.used_at.isoformat() if self.used_at else None
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> 'RenewalCode':
        """Create RenewalCode instance from JSON string"""
        data = json.loads(json_str)
        # Convert ISO format strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data['used_at']:
            data['used_at'] = datetime.fromisoformat(data['used_at'])
        data['status'] = RenewalKeyStatus(data['status'])
        return cls(**data)


class RenewalManager(BaseRedisManager):
    def _get_renewal_key(self, renewal_code: str) -> str:
        """Get the Redis key for storing renewal code information."""
        return f"renewal:{renewal_code}"

    async def create_renewal_code(self, days: int = 0, hours: int = 0, minutes: int = 0, count: int = 1) -> List[str]:
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
                created_at=current_time
            )
            
            await self.set_async(
                self._get_renewal_key(code),
                renewal_code.to_json()
            )
            
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
            await self.set_async(
                self._get_renewal_key(code),
                renewal_code.to_json()
            )

    async def use_renewal_code(self, renewal_code: str, api_key_manager, api_key: str) -> str:
        """
        Use a renewal code to extend an API key's expiration.
        
        Args:
            renewal_code: The renewal code to use
            api_key_manager: Instance of APIKeyManager
            api_key: The API key to extend
            
        Returns:
            str: Success/error message
        """
        code_info = await self.get_renewal_code(renewal_code)
        if not code_info or code_info.status != RenewalKeyStatus.UNUSED:
            return "无效的续费码或该续费码已被使用"

        total_minutes = code_info.total_minutes()
        if total_minutes <= 0:
            return "续费码无效：续期时间必须大于0"

        # Convert minutes to days for the API key manager
        days = total_minutes / (24 * 60)
        result = api_key_manager.extend_api_key_expiration(api_key, days)
        
        if "已延长" in result:
            await self.mark_as_used(renewal_code, api_key)
            
        return result

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
            "used_at": renewal_code.used_at.isoformat() if renewal_code.used_at else None,
            "used_by": renewal_code.used_by
        }