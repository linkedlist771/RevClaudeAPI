from fastapi import APIRouter, Header, Query
from typing import Optional
import httpx

router = APIRouter()

BASE_URL = "http://54.254.143.80:8090"

@router.get("/token_stats")
async def token_stats():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/token_stats")
        return response.json()

@router.post("/audit_limit")
async def audit_limit(
    authorization: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None, alias="User-Agent"),
    host: Optional[str] = Header(None),
):
    headers = {
        "Authorization": authorization,
        "User-Agent": user_agent,
        "Host": host
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/audit_limit", headers=headers)
        return response.json()

@router.get("/logout")
async def logout(
    user_agent_query: Optional[str] = Query(None, alias="User-Agent"),
    auth: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    user_agent_header: Optional[str] = Header(None, alias="User-Agent"),
    host: Optional[str] = Header(None),
):
    params = {
        "User-Agent": user_agent_query,
        "Auth": auth
    }
    headers = {
        "Authorization": authorization,
        "User-Agent": user_agent_header,
        "Host": host
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/logout", params=params, headers=headers)
        return response.json()

@router.get("/devices")
async def devices(
    authorization: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None, alias="User-Agent"),
    host: Optional[str] = Header(None),
):
    headers = {
        "Authorization": authorization,
        "User-Agent": user_agent,
        "Host": host
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/devices", headers=headers)
        return response.json()
