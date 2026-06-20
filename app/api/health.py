from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import get_database
from app.core.responses import success
from app.services.extraction import ocr_health
from app.services.legal_readiness import golden_report_health, legal_runtime_health
from app.services.vector_store import pinecone_store

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    mongo_ok = True
    try:
        await get_database().command("ping")
    except Exception:
        mongo_ok = False
    legal = legal_runtime_health()
    return success(
        "AI agent health retrieved",
        {
            "status": "ok" if mongo_ok and legal["ready"] else "degraded",
            "service": get_settings().APP_NAME,
            "version": get_settings().APP_VERSION,
            "mongodb": mongo_ok,
            "pinecone": await pinecone_store.health(),
            "ocr": ocr_health(),
            "legalGolden": golden_report_health(),
            "legalRuntime": legal,
        },
    )
