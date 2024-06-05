from rev_claude.api_key.api_key_manage import APIKeyManager, get_api_key_manager
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from rev_claude.schemas import CreateAPIKeyRequest

router = APIRouter()


# 假设 APIKeyManager 类已被定义，我们现在创建一个依赖项


# TODO: add the level to justify whether the api key is the plus user.
@router.post("/create_key")
async def create_key(
    create_apikey_request: CreateAPIKeyRequest,
    manager: APIKeyManager = Depends(get_api_key_manager),
):
    """Create an API key with a set expiration time."""
    api_key_type = str(create_apikey_request.key_type)
    expiration_seconds = create_apikey_request.expiration_days * 24 * 60 * 60
    api_keys = []
    for i in range(create_apikey_request.key_number):
        api_key = manager.create_api_key(expiration_seconds, api_key_type)
        api_keys.append(api_key)
    return {"api_key": api_keys}


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


@router.get("/get_information/{api_key}")
async def get_information(
    api_key: str, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Get the usage count of an API key."""
    key_information = manager.get_apikey_information(api_key)
    return key_information


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
    key_information = {}
    for key in api_keys:
        key_information[key] = manager.get_apikey_information(key)
    return key_information


@router.post("/set_key_type/{api_key}")
async def set_key_type(
    api_key: str, key_type: str, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Set the type of an API key."""
    key_type = str(key_type.strip().lower())
    result = manager.set_api_key_type(api_key, key_type)
    return {"message": result}


@router.get("/get_key_type/{api_key}")
async def get_key_type(
    api_key: str, manager: APIKeyManager = Depends(get_api_key_manager)
):
    """Get the type of an API key."""
    key_type = manager.get_api_key_type(api_key)
    return {"api_key": api_key, "key_type": key_type}


@router.post("/add_key/{api_key}")
async def add_key(
    api_key: str,
    expiration_seconds: int,
    api_key_type: str,
    manager: APIKeyManager = Depends(get_api_key_manager),
):
    """Add an existing API key with a specific expiration time."""
    api_key_type = str(api_key_type.strip().lower())
    api_key = manager.add_api_key(api_key, expiration_seconds, api_key_type)
    return {"api_key": api_key}
