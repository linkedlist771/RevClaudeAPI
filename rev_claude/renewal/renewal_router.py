from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from rev_claude.renewal.renewal_manager import RenewalManager
from rev_claude.api_key.api_key_manage import get_api_key_manager
from typing import Optional, List


class CreateRenewalCodeRequest(BaseModel):
    days: int = 0
    hours: int = 0
    minutes: int = 0
    count: int = Field(default=1, ge=1, le=10000)  # 限制单次创建数量在1-10000之间


class UseRenewalCodeRequest(BaseModel):
    renewal_code: str
    api_key: str


router = APIRouter()


def get_renewal_manager():
    return RenewalManager()


@router.post("/create", response_model=List[str])
async def create_renewal_code(
    request: CreateRenewalCodeRequest,
    renewal_manager: RenewalManager = Depends(get_renewal_manager),
):
    """Create multiple renewal codes."""
    try:
        codes = await renewal_manager.create_renewal_code(
            days=request.days,
            hours=request.hours,
            minutes=request.minutes,
            count=request.count
        )
        return codes
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/info/{code}")
async def get_renewal_code_info(
    code: str,
    renewal_manager: RenewalManager = Depends(get_renewal_manager),
):
    """Get information about a renewal code."""
    info = await renewal_manager.get_renewal_code_info(code)
    if "error" in info:
        raise HTTPException(status_code=404, detail=info["error"])
    return info


@router.post("/use")
async def use_renewal_code(
    request: UseRenewalCodeRequest,
    renewal_manager: RenewalManager = Depends(get_renewal_manager),
    api_key_manager=Depends(get_api_key_manager),
):
    """Use a renewal code to extend an API key's expiration."""
    result = await renewal_manager.use_renewal_code(
        request.renewal_code,
        api_key_manager,
        request.api_key
    )
    
    if "无效" in result or "错误" in result:
        raise HTTPException(status_code=400, detail=result)
    
    return {"message": result}


@router.get("/validate/{code}")
async def validate_renewal_code(
    code: str,
    renewal_manager: RenewalManager = Depends(get_renewal_manager),
):
    """Check if a renewal code is valid and unused."""
    is_valid = await renewal_manager.is_valid_renewal_code(code)
    return {"is_valid": is_valid}


@router.get("/all")
async def get_all_renewal_codes(
    renewal_manager: RenewalManager = Depends(get_renewal_manager),
):
    """Get information about all renewal codes."""
    codes = await renewal_manager.get_all_renewal_codes()
    return {
        "total": len(codes),
        "codes": codes
    }
