from fastapi import FastAPI, HTTPException, Request, APIRouter

from claude_router import router as claude_router


router = APIRouter(prefix="/api/v1")
router.include_router(claude_router, prefix="/claude")