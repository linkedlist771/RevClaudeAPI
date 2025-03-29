from fastapi import APIRouter

from rev_claude.api_key.api_key_router import router as api_key_router
from rev_claude.artifacts_sharing.artifacts_sharing_router import \
    router as artifacts_sharing_router
from rev_claude.client.claude_router import router as claude_router
from rev_claude.cookie.claude_cookie_router import \
    router as claude_cookie_router
from rev_claude.devices.devices_router import router as devices_router
from rev_claude.history.conversation_history_router import \
    router as conversation_history_router
from rev_claude.renewal.renewal_router import router as renewal_router
from rev_claude.status.clients_status_router import \
    router as clients_status_router
from rev_claude.gpt_cookie_login.router import router as gpt_login_router

router = APIRouter(prefix="/api/v1")
router.include_router(claude_router, prefix="/claude", tags=["claude"])
router.include_router(api_key_router, prefix="/api_key", tags=["api_key"])
router.include_router(claude_cookie_router, prefix="/cookie", tags=["cookie"])
router.include_router(
    clients_status_router, prefix="/clients_status", tags=["clients_status"]
)
router.include_router(
    conversation_history_router,
    prefix="/conversation_history",
    tags=["conversation_history"],
)
router.include_router(
    artifacts_sharing_router, prefix="/artifacts_sharing", tags=["artifacts_sharing"]
)
router.include_router(devices_router, prefix="/devices", tags=["devices"])
router.include_router(renewal_router, prefix="/renewal", tags=["renewal"])
router.include_router(gpt_login_router, prefix="/gpt_login", tags=["gpt_login"])
