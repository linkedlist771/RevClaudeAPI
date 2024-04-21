import redis
import uuid


class APIKeyManager:
    def __init__(self, host="localhost", port=6379, db=0):
        """Initialize the connection to Redis."""
        self.redis = redis.StrictRedis(host=host, port=port, db=db)

    def create_api_key(self, expiration_seconds):
        """Create a new API key with a specific expiration time."""
        api_key = f"sj-{str(uuid.uuid4()).replace('-', '')}"
        self.redis.setex(api_key, expiration_seconds, "active")
        return api_key

    def is_api_key_valid(self, api_key):
        """Check if an API key is still valid (exists and has not expired)."""
        return self.redis.exists(api_key) == 1

    def increment_usage(self, api_key):
        """Increment the usage count for a given API key."""
        usage_key = f"{api_key}:usage"
        return self.redis.incr(usage_key)

    def get_usage(self, api_key):
        """Retrieve the current usage count of an API key."""
        usage_key = f"{api_key}:usage"
        count = self.redis.get(usage_key)
        return int(count) if count else 0

    def delete_api_key(self, api_key):
        """Delete an API key and its associated usage count."""
        usage_key = f"{api_key}:usage"
        # Pipeline the delete operations to ensure both keys are deleted together
        pipeline = self.redis.pipeline()
        pipeline.delete(api_key)
        pipeline.delete(usage_key)
        pipeline.execute()

    def list_active_api_keys(self):
        """List all active API keys."""
        active_keys = []
        for key in self.redis.scan_iter("sj-*"):  # Assuming all keys start with 'sj-'
            if self.redis.ttl(key) > 0:  # Check if the key has not expired
                active_keys.append(key.decode('utf-8'))
        return active_keys


def get_api_key_manager():
    return APIKeyManager()


# Example usage of the APIKeyManager
if __name__ == "__main__":
    manager = APIKeyManager()
    key = manager.create_api_key(300)
    print("API Key:", key)
    print("Key Valid:", manager.is_api_key_valid(key))
    manager.increment_usage(key)
    manager.increment_usage(key)
    print("Usage Count:", manager.get_usage(key))
    manager.delete_api_key(key)
    print("Key Valid after deletion:", manager.is_api_key_valid(key))