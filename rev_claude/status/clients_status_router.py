import asyncio
from concurrent.futures import ProcessPoolExecutor

from rev_claude.periodic_checks.clients_limit_checks import (
    check_reverse_official_usage_limits,
)
from rev_claude.status.clients_status_manager import ClientsStatusManager
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from rev_claude.status_code.status_code_enum import NORMAL_ERROR

router = APIRouter()


# def set_client_status(self, client_type, client_idx, status):
@router.put("/update_client_status")
async def update_cookie(
    client_type: str,
    client_idx: int,
    status: str,
):
    """Update an existing cookie."""
    try:
        manager = ClientsStatusManager()
        await manager.set_client_status(client_type, client_idx, status)
        return {"message": "Set client status successfully."}
    except Exception as e:
        raise HTTPException(status_code=NORMAL_ERROR, detail=str(e))


@router.get("/check_clients_limits")
async def check_clients_limits():
    loop = asyncio.get_running_loop()
    process_pool = ProcessPoolExecutor(max_workers=1)
    try:
        await loop.run_in_executor(process_pool, check_reverse_official_usage_limits)
        return {"message": "Client limits check completed successfully"}
    except Exception as e:
        return {"error": f"An error occurred during the check: {str(e)}"}
