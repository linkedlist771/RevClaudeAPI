from fastapi import APIRouter
import httpx
from pydantic import BaseModel
from typing import Union
import base64
import json

class LogInRequest(BaseModel):
    account: Union[str, None] = None
    password: Union[str, None] = None
    action: str = 'default'
    encoded_account_and_password: Union[str, None] = None


router = APIRouter()


@router.post("/login")
async def login(login_request: LogInRequest):
    async with httpx.AsyncClient() as client:
        data = None
        if login_request.encoded_account_and_password:
            try:
                # Decode the base64 encoded credentials
                decoded_bytes = base64.b64decode(login_request.encoded_account_and_password)
                decoded_str = decoded_bytes.decode('utf-8')
                credentials = json.loads(decoded_str)
                
                # Extract account and password
                data = {
                    "account": credentials.get("account"),
                    "password": credentials.get("password"),
                    "action": login_request.action
                }
            except Exception as e:
                return {"error": f"Failed to decode credentials: {str(e)}"}
        else:
            data=login_request.model_dump()
        res = await client.post('https://chat.qqyunsd.com/login', json=data)
        cookies_dict = {}
        try:
            for name, value in res.cookies.items():
                cookies_dict[name] = value
        except Exception as e:
            for cookie in res.cookies.jar:
                cookies_dict[cookie.name] = cookie.value

        return cookies_dict
