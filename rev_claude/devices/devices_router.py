from fastapi import APIRouter, Request
import httpx
from loguru import logger

router = APIRouter()

BASE_URL = "http://54.254.143.80:8090"


@router.get("/token_stats")
async def token_stats():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/token_stats")
        return response.json()


@router.post("/audit_limit")
async def audit_limit(request: Request):
    headers = {
        "Authorization": "Bearer " + request.headers.get("Authorization"),
        "User-Agent": request.headers.get("User-Agent"),
        "X-Forwarded-Host": request.headers.get("Host")
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/audit_limit", headers=headers)
        return response.json()


@router.get("/logout")
async def logout(request: Request):
    params = {}
    headers = {
        "Authorization": "Bearer " + request.headers.get("Authorization"),
        "User-Agent": request.headers.get("User-Agent"),
        # "X-Forwarded-Host": request.headers.get("Host")
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/logout", params=params, headers=headers)
            res = response.json()
            logger.debug(res)
            return res
    except Exception as e:
        from traceback import format_exc
        logger.error(format_exc())
        return format_exc()


@router.get("/devices")
async def devices(request: Request):
    headers = {
        "Authorization": "Bearer " + request.headers.get("Authorization"),
        "User-Agent": request.headers.get("User-Agent"),
        "X-Forwarded-Host": request.headers.get("Host")
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/devices", headers=headers)
        return response.json()


@router.get("/all_token_devices")
async def all_token_devices(request: Request):
    headers = {
        # "Authorization": "Bearer " + request.headers.get("Authorization"),
        # "User-Agent": request.headers.get("User-Agent"),
        # "X-Forwarded-Host": request.headers.get("Host")
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/all_token_devices", headers=headers)
        return response.json()
