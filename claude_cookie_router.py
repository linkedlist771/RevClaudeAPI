from claude_cookie_manage import CookieManager, CookieKeyType, get_cookie_manager
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/upload_cookie")
async def upload_cookie(
    cookie: str,
    cookie_type: CookieKeyType = CookieKeyType.BASIC.value,
    account: str = "",
    manager: CookieManager = Depends(get_cookie_manager),
):
    """Upload a new cookie."""
    cookie_key = manager.upload_cookie(cookie, cookie_type.value, account)
    return {"cookie_key": cookie_key}


@router.put("/update_cookie/{cookie_key}")
async def update_cookie(
    cookie_key: str,
    cookie: str,
    account: str = "",
    manager: CookieManager = Depends(get_cookie_manager),
):
    """Update an existing cookie."""
    try:
        result = manager.update_cookie(cookie_key, cookie, account)
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/delete_cookie/{cookie_key}")
async def delete_cookie(
    cookie_key: str, manager: CookieManager = Depends(get_cookie_manager)
):
    """Delete a cookie."""
    try:
        result = manager.delete_cookie(cookie_key)
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cookie_status/{cookie_key}")
async def get_cookie_status(
    cookie_key: str, manager: CookieManager = Depends(get_cookie_manager)
):
    """Get the status of a cookie."""
    status = manager.get_cookie_status(cookie_key)
    return {"status": status}


@router.get("/all_cookies/{cookie_type}")
async def get_all_cookies(
    cookie_type: str, manager: CookieManager = Depends(get_cookie_manager)
):
    """Get all cookies of a specific type."""
    cookies,cookie_keys = manager.get_all_cookies(cookie_type)
    return {"cookies": cookies, "cookie_keys": cookie_keys}


@router.get("/list_all_cookies")
async def list_all_cookies(manager: CookieManager = Depends(get_cookie_manager)):
    """List all cookies."""
    cookies = manager.get_all_cookie_status()
    return {"cookies": cookies}
