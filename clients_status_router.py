from clients_status_manager import ClientsStatusManager
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

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
        manager.set_client_status(client_type, client_idx, status)
        return {"message": "Set client status successfully."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))



