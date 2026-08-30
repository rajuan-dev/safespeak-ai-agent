from fastapi import APIRouter, Request, status

from app.core.responses import success

from .dependencies import AuthenticatedSessionOrUser
from .schema import (
    AdvocateQueryInput,
    AdvocateRequestInput,
    CancelAdvocateRequestInput,
    HelpSupportRequestInput,
    OwnedAdvocateRequestQueryInput,
    RecommendationsInput,
    SafetyPlanInput,
    ServicesQueryInput,
    UpdateSafetyPlanInput,
    WarmReferralInput,
)
from .service import (
    cancel_owned_advocate_request,
    create_advocate_request,
    create_help_support_request,
    create_safety_plan,
    create_warm_referral,
    get_owned_advocate_request,
    get_recommendations,
    get_support_service_by_id,
    list_advocates,
    list_owned_advocate_requests,
    list_safety_plans,
    list_support_services,
    update_safety_plan,
)

router = APIRouter(prefix="/support", tags=["support"])


def _context(request: Request, principal: AuthenticatedSessionOrUser) -> dict[str, object]:
    return {
        "owner": {"userId": principal.user_id, "sessionId": principal.session_id},
        "ip": request.client.host if request.client else None,
        "userAgent": request.headers.get("user-agent"),
    }


@router.get("/services")
async def list_services_route(
    request: Request,
    principal: AuthenticatedSessionOrUser,
    query: ServicesQueryInput = None,
):
    services = await list_support_services(
        _context(request, principal), query or ServicesQueryInput()
    )
    return success("Support services retrieved", {"services": services})


@router.get("/services/{id}")
async def get_service_route(request: Request, id: str, principal: AuthenticatedSessionOrUser):
    service = await get_support_service_by_id(_context(request, principal), id)
    return success("Support service retrieved", {"service": service})


@router.post("/recommendations")
async def recommendations_route(
    request: Request,
    input_data: RecommendationsInput,
    principal: AuthenticatedSessionOrUser,
):
    recommendations = await get_recommendations(_context(request, principal), input_data)
    return success("Support recommendations retrieved", {"recommendations": recommendations})


@router.get("/advocates")
async def list_advocates_route(
    request: Request,
    principal: AuthenticatedSessionOrUser,
    query: AdvocateQueryInput = None,
):
    payload = await list_advocates(_context(request, principal), query or AdvocateQueryInput())
    return success("Support advocates retrieved", payload)


@router.post("/warm-referral", status_code=status.HTTP_201_CREATED)
async def warm_referral_route(
    request: Request,
    input_data: WarmReferralInput,
    principal: AuthenticatedSessionOrUser,
):
    referral = await create_warm_referral(_context(request, principal), input_data)
    return success("Warm referral requested", {"referral": referral})


@router.post("/advocate-request", status_code=status.HTTP_201_CREATED)
async def advocate_request_route(
    request: Request,
    input_data: AdvocateRequestInput,
    principal: AuthenticatedSessionOrUser,
):
    advocate_request = await create_advocate_request(_context(request, principal), input_data)
    return success("Advocate request created", {"request": advocate_request})


@router.get("/advocate-requests/me")
async def list_owned_advocate_requests_route(
    request: Request,
    principal: AuthenticatedSessionOrUser,
    query: OwnedAdvocateRequestQueryInput = None,
):
    requests = await list_owned_advocate_requests(
        _context(request, principal), query or OwnedAdvocateRequestQueryInput()
    )
    return success("Advocate requests retrieved", {"requests": requests})


@router.get("/advocate-requests/{id}")
async def get_owned_advocate_request_route(
    request: Request,
    id: str,
    principal: AuthenticatedSessionOrUser,
):
    advocate_request = await get_owned_advocate_request(_context(request, principal), id)
    return success("Advocate request retrieved", {"request": advocate_request})


@router.patch("/advocate-requests/{id}/cancel")
async def cancel_owned_advocate_request_route(
    request: Request,
    id: str,
    input_data: CancelAdvocateRequestInput,
    principal: AuthenticatedSessionOrUser,
):
    advocate_request = await cancel_owned_advocate_request(
        _context(request, principal), id, input_data
    )
    return success("Advocate request cancelled", {"request": advocate_request})


@router.post("/help-request", status_code=status.HTTP_201_CREATED)
async def help_support_request_route(
    request: Request,
    input_data: HelpSupportRequestInput,
    principal: AuthenticatedSessionOrUser,
):
    help_request = await create_help_support_request(_context(request, principal), input_data)
    return success("Help support request created", {"request": help_request})


@router.get("/safety-plans")
async def list_safety_plans_route(request: Request, principal: AuthenticatedSessionOrUser):
    safety_plans = await list_safety_plans(_context(request, principal))
    return success("Safety plans retrieved", {"safetyPlans": safety_plans})


@router.post("/safety-plans", status_code=status.HTTP_201_CREATED)
async def create_safety_plan_route(
    request: Request,
    input_data: SafetyPlanInput,
    principal: AuthenticatedSessionOrUser,
):
    safety_plan = await create_safety_plan(_context(request, principal), input_data)
    return success("Safety plan created", {"safetyPlan": safety_plan})


@router.patch("/safety-plans/{id}")
async def update_safety_plan_route(
    request: Request,
    id: str,
    input_data: UpdateSafetyPlanInput,
    principal: AuthenticatedSessionOrUser,
):
    safety_plan = await update_safety_plan(_context(request, principal), id, input_data)
    return success("Safety plan updated", {"safetyPlan": safety_plan})
