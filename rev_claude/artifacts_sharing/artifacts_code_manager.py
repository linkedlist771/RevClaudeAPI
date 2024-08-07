import hashlib
from redis.asyncio import Redis
from typing import List

from rev_claude.configs import REDIS_HOST, REDIS_PORT


class ArtifactsCodeManager:
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=1):
        """Initialize the connection to Redis."""
        self.aioredis = None

    async def get_aioredis(self):
        if self.aioredis is None:
            self.aioredis = await Redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/1")
        return self.aioredis

    async def upload_code(self, code: str) -> str:
        """Upload a code snippet and return a hash."""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        redis = await self.get_aioredis()
        await redis.set(f"code:{code_hash}", code)
        return code_hash

    async def get_code(self, code_hash: str) -> str:
        """Retrieve a code snippet by its hash."""
        redis = await self.get_aioredis()
        code = await redis.get(f"code:{code_hash}")
        if code is None:
            # raise ValueError("Code not found")
            code = "Code not found"
        if isinstance(code, bytes):
            code = code.decode("utf-8")
        # code = code.decode("utf-8")
        return code

    async def delete_code(self, code_hash: str) -> bool:
        """Delete a code snippet by its hash."""
        redis = await self.get_aioredis()
        result = await redis.delete(f"code:{code_hash}")
        return result == 1

    async def list_all_codes(self) -> List[str]:
        """List all code hashes."""
        redis = await self.get_aioredis()
        keys = await redis.keys("code:*")
        return [key.decode("utf-8").split(":")[1] for key in keys]
