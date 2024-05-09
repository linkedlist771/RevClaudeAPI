from fastapi import FastAPI, HTTPException, Request, APIRouter

from claude_router import router as claude_router
from api_key_router import router as api_key_router
from claude_cookie_router import router as claude_cookie_router
from clients_status_router import router as clients_status_router
from conversation_history_router import router as conversation_history_router

router = APIRouter(prefix="/api/v1")
router.include_router(claude_router, prefix="/claude")
router.include_router(api_key_router, prefix="/api_key")
router.include_router(claude_cookie_router, prefix="/cookie")
router.include_router(clients_status_router, prefix="/clients_status")
router.include_router(conversation_history_router, prefix="/conversation_history")
