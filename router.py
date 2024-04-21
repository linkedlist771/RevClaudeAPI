from fastapi import FastAPI, HTTPException, Request, APIRouter

from claude_router import router as claude_router
from api_key_router import router as api_key_router

router = APIRouter(prefix="/api/v1")
router.include_router(claude_router, prefix="/claude")
router.include_router(api_key_router, prefix="/api_key")