import json
from typing import Any

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.services.extraction import ocr_health


def golden_report_health() -> dict[str, Any]:
    settings = get_settings()
    path = settings.LEGAL_GOLDEN_REPORT_PATH
    if not path.exists():
        return {
            "required": settings.LEGAL_REQUIRE_PRODUCTION_GOLDEN,
            "ready": False,
            "reportPath": str(path),
            "message": "Production legal golden report has not been generated.",
        }
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "required": settings.LEGAL_REQUIRE_PRODUCTION_GOLDEN,
            "ready": False,
            "reportPath": str(path),
            "message": f"Golden report could not be read: {exc}",
        }
    return {
        "required": settings.LEGAL_REQUIRE_PRODUCTION_GOLDEN,
        "ready": bool(report.get("productionReady")),
        "reportPath": str(path),
        "realFixtureCount": report.get("realFixtureCount", 0),
        "jurisdictionCount": report.get("jurisdictionCount", 0),
        "totalQuestions": report.get("totalQuestions", 0),
        "blockers": report.get("productionBlockers", []),
        "message": (
            "Reviewed legal golden corpus passed"
            if report.get("productionReady")
            else "Reviewed legal golden corpus has not passed"
        ),
    }


def legal_runtime_health() -> dict[str, Any]:
    settings = get_settings()
    golden = golden_report_health()
    ocr = ocr_health()
    blockers: list[str] = []
    if settings.LEGAL_REQUIRE_PRODUCTION_GOLDEN and not golden.get("ready"):
        blockers.append("reviewed_legal_golden_corpus_not_ready")
    if settings.RAG_ENABLE_OCR and not ocr.get("ready"):
        blockers.append("ocr_not_ready")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "golden": golden,
        "ocr": ocr,
    }


def assert_legal_runtime_ready() -> None:
    settings = get_settings()
    if settings.ENVIRONMENT != "production":
        return
    health = legal_runtime_health()
    if not health["ready"]:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Legal RAG is not production-ready: {', '.join(health['blockers'])}",
        )
