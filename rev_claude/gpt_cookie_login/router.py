from fastapi import APIRouter
import httpx
from pydantic import BaseModel


class LogInRequest(BaseModel):
    account: str
    password: str
    action: str = 'default'


router = APIRouter()


@router.post("/login")
async def login(login_request: LogInRequest):
    async with httpx.AsyncClient() as client:
        res = await client.post('https://chat.qqyunsd.com/login', data=login_request.model_dump())
        return res.cookies.get_dict()
