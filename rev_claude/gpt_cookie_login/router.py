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
        # Convert cookies to a dictionary, handling potential duplicate cookies
        cookies_dict = {}
        try:
            # This approach might raise CookieConflict if duplicate cookie names exist
            for name, value in res.cookies.items():
                cookies_dict[name] = value
        except Exception as e:
            # Alternative approach using the cookie jar
            for cookie in res.cookies.jar:
                cookies_dict[cookie.name] = cookie.value

        return cookies_dict
