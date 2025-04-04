from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from rev_claude.api_key.api_key_manage import APIKeyManager, get_api_key_manager
from rev_claude.artifacts_sharing.artifacts_code_manager import ArtifactsCodeManager
from rev_claude.schemas import ArtifactsCodeUploadRequest
from rev_claude.status_code.status_code_enum import HTTP_480_API_KEY_INVALID

router = APIRouter()


async def validate_api_key(request: Request):
    api_manager = get_api_key_manager()
    api_key = request.headers.get("Authorization")
    # logger.info(f"checking api key: {api_key}")
    if api_key is None or not api_manager.is_api_key_valid(api_key):
        raise HTTPException(
            status_code=HTTP_480_API_KEY_INVALID,
            detail="APIKEY已经过期或者不存在，请检查您的APIKEY是否正确。",
        )
    # 尝试激活 API key
    active_message = api_manager.activate_api_key(api_key)


def get_artifacts_code_manager():
    return ArtifactsCodeManager()


@router.post("/upload_code")
async def upload_code(
    request: Request,
    artifacts_upload_request: ArtifactsCodeUploadRequest = Body(...),
    manager: ArtifactsCodeManager = Depends(get_artifacts_code_manager),
):
    """Upload a code snippet and return its hash."""
    await validate_api_key(request)
    code_hash = await manager.upload_code(artifacts_upload_request.code)
    return JSONResponse(
        content={"message": "Code uploaded successfully.", "code_hash": code_hash}
    )


@router.get("/get_code/{code_hash}")
async def get_code(
    code_hash: str, manager: ArtifactsCodeManager = Depends(get_artifacts_code_manager)
):
    """Retrieve a code snippet by its hash."""
    try:
        code = await manager.get_code(code_hash)
        return JSONResponse(content={"code": code})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/delete_code/{code_hash}")
async def delete_code(
    code_hash: str, manager: ArtifactsCodeManager = Depends(get_artifacts_code_manager)
):
    """Delete a code snippet by its hash."""
    result = await manager.delete_code(code_hash)
    if result:
        return JSONResponse(
            content={"message": f"Code {code_hash} has been deleted successfully."}
        )
    else:
        raise HTTPException(status_code=404, detail="Code not found")


@router.get("/list_codes")
async def list_codes(
    manager: ArtifactsCodeManager = Depends(get_artifacts_code_manager),
):
    """List all code hashes."""
    code_hashes = await manager.list_all_codes()
    return JSONResponse(content={"code_hashes": code_hashes})
