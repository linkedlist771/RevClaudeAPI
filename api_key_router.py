from api_key_manage import APIKeyManager, get_api_key_manager
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse


router = APIRouter()


# 假设 APIKeyManager 类已被定义，我们现在创建一个依赖项


# TODO: add the level to justify whether the api key is the plus user.
@router.post("/create_key")
async def create_key(
    expiration_seconds: int, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Create an API key with a set expiration time."""
    api_key = manager.create_api_key(expiration_seconds)
    return {"api_key": api_key}


@router.get("/validate_key/{api_key}")
async def validate_key(
    api_key: str, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Check if an API key is valid."""
    is_valid = manager.is_api_key_valid(api_key)
    return {"is_valid": is_valid}


@router.post("/increment_usage/{api_key}")
async def increment_usage(
    api_key: str, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Increment the usage count of an API key."""
    try:
        usage = manager.increment_usage(api_key)
        return {"api_key": api_key, "usage_count": usage}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/get_usage/{api_key}")
async def get_usage(
    api_key: str, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Get the usage count of an API key."""
    usage = manager.get_usage(api_key)
    return {"api_key": api_key, "usage_count": usage}


@router.delete("/delete_key/{api_key}")
async def delete_key(
    api_key: str, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Delete an API key and its usage count."""
    manager.delete_api_key(api_key)
    return JSONResponse(status_code=204)

@router.get("/list_keys")
async def list_keys(manager: APIKeyManager = Depends(get_api_key_manager)):
    """List all active API keys."""
    api_keys = manager.list_active_api_keys()
    return {"api_keys": api_keys}
