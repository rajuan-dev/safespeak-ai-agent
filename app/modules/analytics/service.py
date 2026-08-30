from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .model import ANALYTICS_EXPORT_EPSILON, ANALYTICS_MINIMUM_CELL_SUPPRESSION
from .repository import AnalyticsRepository, get_analytics_repository
from .schema import AnalyticsExportQueryInput, AnalyticsQueryInput


def _base_match(query: AnalyticsQueryInput) -> dict[str, Any]:
    match: dict[str, Any] = {
        "deletedAt": {"$exists": False},
        "consentSnapshot.use_anonymised_analytics": True,
    }
    if query.jurisdiction:
        match["jurisdiction"] = query.jurisdiction
    if query.language:
        match["language"] = query.language
    return match


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _within_range(item: dict[str, Any], query: AnalyticsQueryInput) -> bool:
    created_at = _coerce_datetime(item.get("createdAt"))
    if not created_at:
        return True
    if query.from_date:
        from_dt = _coerce_datetime(f"{query.from_date}T00:00:00+00:00")
        if from_dt and created_at < from_dt:
            return False
    if query.to_date:
        to_dt = _coerce_datetime(f"{query.to_date}T23:59:59+00:00")
        if to_dt and created_at > to_dt:
            return False
    return True


def _filtered_reports(reports: list[dict[str, Any]], query: AnalyticsQueryInput) -> list[dict[str, Any]]:
    return [report for report in reports if _within_range(report, query)]


def _suppressed_bucket(identifier: Any, count: int) -> dict[str, Any]:
    return {"_id": identifier, "count": count}


def _apply_suppression(counter: Counter) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, count in counter.items():
        if count < ANALYTICS_MINIMUM_CELL_SUPPRESSION:
            continue
        rows.append(_suppressed_bucket(key, count))
    return sorted(rows, key=lambda row: row["count"], reverse=True)


async def get_analytics_overview(
    query: AnalyticsQueryInput,
    *,
    repository: AnalyticsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_analytics_repository()
    reports = _filtered_reports(await repository.list_reports(_base_match(query)), query)
    by_status = _apply_suppression(Counter(report.get("status") for report in reports if report.get("status")))
    by_severity = _apply_suppression(
        Counter(report.get("severity") for report in reports if report.get("severity"))
    )
    return {
        "totalReports": len(reports),
        "byStatus": by_status,
        "bySeverity": by_severity,
        "privacy": {
            "anonymisedOnly": True,
            "minimumCellSuppression": ANALYTICS_MINIMUM_CELL_SUPPRESSION,
        },
    }


async def get_analytics_heatmap(
    query: AnalyticsQueryInput,
    *,
    repository: AnalyticsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_analytics_repository()
    reports = _filtered_reports(await repository.list_reports(_base_match(query)), query)
    counter: Counter = Counter()
    for report in reports:
        key = {
            "jurisdiction": report.get("jurisdiction"),
            "lga": report.get("location", {}).get("lga") if isinstance(report.get("location"), dict) else None,
        }
        counter[(key["jurisdiction"], key["lga"])] += 1
    rows = []
    for (jurisdiction, lga), count in counter.items():
        if count < ANALYTICS_MINIMUM_CELL_SUPPRESSION:
            continue
        rows.append({"_id": {"jurisdiction": jurisdiction, "lga": lga}, "count": count})
    return sorted(rows, key=lambda row: row["count"], reverse=True)


async def get_analytics_trends(
    query: AnalyticsQueryInput,
    *,
    repository: AnalyticsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_analytics_repository()
    reports = _filtered_reports(await repository.list_reports(_base_match(query)), query)
    counter: Counter = Counter()
    for report in reports:
        created_at = _coerce_datetime(report.get("createdAt"))
        if not created_at:
            continue
        counter[created_at.date().isoformat()] += 1
    return [{"_id": key, "count": count} for key, count in sorted(counter.items())]


async def get_analytics_categories(
    query: AnalyticsQueryInput,
    *,
    repository: AnalyticsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_analytics_repository()
    reports = _filtered_reports(await repository.list_reports(_base_match(query)), query)
    return _apply_suppression(
        Counter(report.get("incidentType") for report in reports if report.get("incidentType"))
    )


async def get_analytics_languages(
    query: AnalyticsQueryInput,
    *,
    repository: AnalyticsRepository | None = None,
) -> list[dict[str, Any]]:
    repository = repository or get_analytics_repository()
    reports = _filtered_reports(await repository.list_reports(_base_match(query)), query)
    return _apply_suppression(Counter(report.get("language") for report in reports if report.get("language")))


async def get_analytics_export(
    query: AnalyticsExportQueryInput,
    *,
    repository: AnalyticsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_analytics_repository()
    overview = await get_analytics_overview(query, repository=repository)
    categories = await get_analytics_categories(query, repository=repository)
    languages = await get_analytics_languages(query, repository=repository)
    trends = await get_analytics_trends(query, repository=repository)
    heatmap = await get_analytics_heatmap(query, repository=repository)
    return {
        "exportId": f"analytics-{uuid4().hex[:12]}",
        "format": "csv" if query.format == "csv" else "json",
        "generatedAt": datetime.now(UTC).isoformat(),
        "filters": query.model_dump(by_alias=True),
        "privacy": {
            "anonymisedOnly": True,
            "consentedReportsOnly": True,
            "rawReportsExposed": False,
            "piiExposed": False,
            "minimumCellSuppression": ANALYTICS_MINIMUM_CELL_SUPPRESSION,
            "differentialPrivacy": {
                "enabled": False,
                "mechanism": "disabled_for_contract_parity",
                "epsilon": ANALYTICS_EXPORT_EPSILON,
                "sensitivity": 1,
                "maxAbsoluteNoise": 0,
                "appliedTo": ["summary", "dimensions"],
                "lowCountCellsSuppressedBeforeNoise": True,
                "negativeCountsClampedToZero": True,
            },
        },
        "summary": {
            "reports": {
                "count": overview["totalReports"],
                "suppressed": False,
                "label": "Consented anonymised reports",
                "noiseApplied": False,
            }
        },
        "dimensions": {
            "categories": [{**row, "suppressed": False, "label": "visible", "noiseApplied": False} for row in categories],
            "languages": [{**row, "suppressed": False, "label": "visible", "noiseApplied": False} for row in languages],
            "trends": [{**row, "suppressed": False, "label": "visible", "noiseApplied": False} for row in trends],
            "heatmap": [{**row, "suppressed": False, "label": "visible", "noiseApplied": False} for row in heatmap],
        },
        "rows": [],
    }


async def get_public_local_intelligence(
    query: AnalyticsQueryInput,
    *,
    repository: AnalyticsRepository | None = None,
) -> dict[str, Any]:
    repository = repository or get_analytics_repository()
    categories = await get_analytics_categories(query, repository=repository)
    languages = await get_analytics_languages(query, repository=repository)
    trends = await get_analytics_trends(query, repository=repository)
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "privacy": {
            "minimumCellSuppression": ANALYTICS_MINIMUM_CELL_SUPPRESSION,
            "anonymisedOnly": True,
            "rawReportsExposed": False,
        },
        "categories": categories,
        "languages": languages,
        "trends": trends,
    }
