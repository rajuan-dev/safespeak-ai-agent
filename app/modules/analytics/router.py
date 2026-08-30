from fastapi import APIRouter

from app.core.responses import success

from .dependencies import CurrentAnalyticsAdmin
from .schema import AnalyticsExportQueryInput, AnalyticsQueryInput
from .service import (
    get_analytics_categories,
    get_analytics_export,
    get_analytics_heatmap,
    get_analytics_languages,
    get_analytics_overview,
    get_analytics_trends,
    get_public_local_intelligence,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
admin_router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


@router.get("/public/local-intelligence")
async def public_local_intelligence_route(query: AnalyticsQueryInput = None):
    payload = await get_public_local_intelligence(query or AnalyticsQueryInput())
    return success("Public local intelligence retrieved", {"intelligence": payload})


@admin_router.get("/overview")
async def admin_analytics_overview_route(
    principal: CurrentAnalyticsAdmin,
    query: AnalyticsQueryInput = None,
):
    overview = await get_analytics_overview(query or AnalyticsQueryInput())
    return success("Analytics overview retrieved", {"overview": overview})


@admin_router.get("/heatmap")
async def admin_analytics_heatmap_route(
    principal: CurrentAnalyticsAdmin,
    query: AnalyticsQueryInput = None,
):
    heatmap = await get_analytics_heatmap(query or AnalyticsQueryInput())
    return success("Analytics heatmap retrieved", {"heatmap": heatmap})


@admin_router.get("/trends")
async def admin_analytics_trends_route(
    principal: CurrentAnalyticsAdmin,
    query: AnalyticsQueryInput = None,
):
    trends = await get_analytics_trends(query or AnalyticsQueryInput())
    return success("Analytics trends retrieved", {"trends": trends})


@admin_router.get("/categories")
async def admin_analytics_categories_route(
    principal: CurrentAnalyticsAdmin,
    query: AnalyticsQueryInput = None,
):
    categories = await get_analytics_categories(query or AnalyticsQueryInput())
    return success("Analytics categories retrieved", {"categories": categories})


@admin_router.get("/languages")
async def admin_analytics_languages_route(
    principal: CurrentAnalyticsAdmin,
    query: AnalyticsQueryInput = None,
):
    languages = await get_analytics_languages(query or AnalyticsQueryInput())
    return success("Analytics languages retrieved", {"languages": languages})


@admin_router.get("/export")
async def admin_analytics_export_route(
    principal: CurrentAnalyticsAdmin,
    query: AnalyticsExportQueryInput = None,
):
    export = await get_analytics_export(query or AnalyticsExportQueryInput())
    return success("Analytics export generated", {"export": export})
