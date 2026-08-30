import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.modules.admin import service as admin_service_module
from app.modules.audit import service as audit_service_module
from app.modules.auth.model import AuthenticatedUserPayload
from app.modules.auth.repository import get_auth_repository
from app.modules.auth.security import build_auth_tokens
from app.modules.content import service as content_service_module
from app.modules.platform_settings import service as platform_settings_service_module
from app.modules.resources import service as resources_service_module


def _now() -> datetime:
    return datetime.now(UTC)


class FakeAuthRepository:
    def __init__(self) -> None:
        now = _now()
        self.users = {
            "507f1f77bcf86cd799439012": {
                "_id": "507f1f77bcf86cd799439012",
                "email": "admin@example.com",
                "passwordHash": "x",
                "fullName": "Admin User",
                "role": "super_admin",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439014": {
                "_id": "507f1f77bcf86cd799439014",
                "email": "content@example.com",
                "passwordHash": "x",
                "fullName": "Content User",
                "role": "content_admin",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439015": {
                "_id": "507f1f77bcf86cd799439015",
                "email": "analytics@example.com",
                "passwordHash": "x",
                "fullName": "Analytics User",
                "role": "analytics_viewer",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439016": {
                "_id": "507f1f77bcf86cd799439016",
                "email": "integration@example.com",
                "passwordHash": "x",
                "fullName": "Integration User",
                "role": "integration_admin",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
            "507f1f77bcf86cd799439011": {
                "_id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "passwordHash": "x",
                "fullName": "Public User",
                "role": "public_user",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            },
        }

    async def find_user_by_id(self, user_id: str):
        return self.users.get(user_id)


class FakeAdminRepository:
    def __init__(self) -> None:
        now = _now()
        self.users = {
            "507f1f77bcf86cd799439099": {
                "_id": ObjectId("507f1f77bcf86cd799439099"),
                "email": "managed@example.com",
                "fullName": "Managed User",
                "role": "public_user",
                "status": "active",
                "createdAt": now,
                "updatedAt": now,
            }
        }
        self.privacy_requests = {
            "507f1f77bcf86cd799439081": {
                "_id": ObjectId("507f1f77bcf86cd799439081"),
                "requestType": "data_export",
                "status": "pending",
                "createdAt": now,
            }
        }
        self.destinations = {}
        self.templates = {}
        self.knowledge_sources = [
            {"_id": ObjectId("507f1f77bcf86cd799439082"), "title": "Knowledge", "status": "approved"}
        ]
        self.content_resources = [
            {"_id": ObjectId("507f1f77bcf86cd799439083"), "name": "Guide", "status": "published"}
        ]
        self.microeducation = [
            {"_id": ObjectId("507f1f77bcf86cd799439084"), "title": "Card", "status": "published"}
        ]
        self.report_deliveries = [
            {"_id": ObjectId("507f1f77bcf86cd799439085"), "status": "submitted", "destinationType": "police"}
        ]
        self.support_services = {}
        self.warm_referrals = {
            "507f1f77bcf86cd799439086": {
                "_id": ObjectId("507f1f77bcf86cd799439086"),
                "status": "pending",
                "serviceId": "svc-1",
                "createdAt": now,
            }
        }
        self.audit_logs = [
            {
                "_id": ObjectId("507f1f77bcf86cd799439087"),
                "action": "REPORT_CREATED",
                "resourceType": "report",
                "createdAt": now,
            }
        ]
        self.ai_interactions = [{}]
        self.reports = [{}, {}]
        self.notification_reads = {}

    async def count_documents(self, collection_name, query):
        mapping = {
            "users": len(self.users),
            "reports": len(self.reports),
            "rag_sources": len(self.knowledge_sources),
            "privacy_requests": sum(
                1
                for item in self.privacy_requests.values()
                if not query or item.get("status") in query.get("status", {}).get("$in", [item.get("status")])
            ),
            "ai_interactions": len(self.ai_interactions),
            "content_resources": len(self.content_resources),
        }
        return mapping.get(collection_name, 0)

    async def list_users(self, query, limit):
        rows = list(self.users.values())
        if query.get("role"):
            rows = [row for row in rows if row["role"] == query["role"]]
        if query.get("status"):
            rows = [row for row in rows if row["status"] == query["status"]]
        return rows[:limit]

    async def create_user(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.users[str(record["_id"])] = record
        return record

    async def update_user(self, user_id, updates):
        key = user_id if user_id in self.users else next(iter(self.users))
        record = self.users[key]
        record.update(updates)
        record["updatedAt"] = _now()
        return record

    async def list_privacy_requests(self, query, limit):
        rows = list(self.privacy_requests.values())
        if query.get("status"):
            rows = [row for row in rows if row["status"] == query["status"]]
        return rows[:limit]

    async def update_privacy_request(self, request_id, updates):
        record = self.privacy_requests[request_id]
        record.update(updates)
        return record

    async def list_destinations(self, query):
        return list(self.destinations.values())

    async def create_destination(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.destinations[str(record["_id"])] = record
        return record

    async def update_destination(self, destination_id, updates):
        record = self.destinations[destination_id]
        record.update(updates)
        return record

    async def list_templates(self, query):
        return list(self.templates.values())

    async def create_template(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.templates[str(record["_id"])] = record
        return record

    async def update_template(self, template_id, updates):
        record = self.templates[template_id]
        record.update(updates)
        return record

    async def list_report_deliveries(self, query, limit):
        return self.report_deliveries[:limit]

    async def list_knowledge_sources(self):
        return self.knowledge_sources

    async def list_educational_content(self):
        return {"resources": self.content_resources, "microeducation": self.microeducation}

    async def list_support_services(self, query):
        return list(self.support_services.values())

    async def create_support_service(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.support_services[str(record["_id"])] = record
        return record

    async def update_support_service(self, service_id, updates):
        record = self.support_services[service_id]
        record.update(updates)
        return record

    async def delete_support_service(self, service_id):
        return self.support_services.get(service_id)

    async def list_warm_referrals(self, query, limit):
        rows = list(self.warm_referrals.values())
        if query.get("status"):
            rows = [row for row in rows if row["status"] == query["status"]]
        return rows[:limit]

    async def update_warm_referral(self, referral_id, updates):
        record = self.warm_referrals[referral_id]
        record.update(updates)
        return record

    async def list_recent_audit_logs(self, limit):
        return self.audit_logs[:limit]

    async def find_notification_read(self, admin_user_id, notification_id):
        return self.notification_reads.get((admin_user_id, notification_id))

    async def mark_notification_read(self, admin_user_id, notification_id):
        record = {"_id": ObjectId(), "adminUserId": admin_user_id, "notificationId": notification_id}
        self.notification_reads[(admin_user_id, notification_id)] = record
        return record

    async def mark_notifications_read_all(self, admin_user_id, notification_ids):
        for notification_id in notification_ids:
            await self.mark_notification_read(admin_user_id, notification_id)
        return len(notification_ids)


class FakeContentRepository:
    def __init__(self) -> None:
        now = _now()
        self.resources = {}
        self.categories = {
            "507f1f77bcf86cd799439090": {
                "_id": ObjectId("507f1f77bcf86cd799439090"),
                "name": "Safety",
                "status": "published",
                "backgroundColor": "#000",
                "textColor": "#fff",
                "sortOrder": 0,
                "createdAt": now,
                "updatedAt": now,
            }
        }
        self.items = {}

    async def list_content_resources(self, query):
        return list(self.resources.values())

    async def get_content_resource(self, resource_id):
        return self.resources.get(resource_id)

    async def create_content_resource(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.resources[str(record["_id"])] = record
        return record

    async def update_content_resource(self, resource_id, updates):
        record = self.resources.get(resource_id)
        if not record:
            return None
        record.update(updates)
        return record

    async def delete_content_resource(self, resource_id):
        return self.resources.get(resource_id)

    async def list_microeducation(self, query):
        rows = list(self.items.values())
        if query.get("categoryId"):
            rows = [row for row in rows if row.get("categoryId") == query["categoryId"]]
        return rows

    async def get_microeducation(self, item_id):
        return self.items.get(item_id)

    async def create_microeducation(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.items[str(record["_id"])] = record
        return record

    async def update_microeducation(self, item_id, updates):
        record = self.items.get(item_id)
        if not record:
            return None
        record.update(updates)
        return record

    async def delete_microeducation(self, item_id):
        return self.items.get(item_id)

    async def list_microeducation_categories(self, query):
        return list(self.categories.values())

    async def get_microeducation_category(self, category_id):
        return self.categories.get(category_id)

    async def create_microeducation_category(self, payload):
        record = {"_id": ObjectId(), "createdAt": _now(), "updatedAt": _now(), **payload}
        self.categories[str(record["_id"])] = record
        return record

    async def update_microeducation_category(self, category_id, updates):
        record = self.categories.get(category_id)
        if not record:
            return None
        record.update(updates)
        return record

    async def delete_microeducation_category(self, category_id):
        return self.categories.get(category_id)


class FakePlatformSettingsRepository:
    def __init__(self) -> None:
        self.document = {
            "_id": ObjectId(),
            "draft": {
                "safety": {"immediateDangerText": "Call now"},
                "consent": {"introText": "Consent"},
                "ai": {"disclaimerText": "Info only"},
            },
            "published": {
                "safety": {"immediateDangerText": "Call now"},
                "consent": {"introText": "Consent"},
                "ai": {"disclaimerText": "Info only"},
            },
            "version": 1,
            "createdAt": _now(),
            "updatedAt": _now(),
        }

    async def get_or_create(self):
        return self.document

    async def update_draft(self, payload):
        self.document.update(payload)
        return self.document

    async def publish(self, published_payload, published_by):
        self.document["published"] = published_payload
        self.document["publishedBy"] = published_by
        self.document["version"] += 1
        return self.document


class FakeResourcesRepository:
    def __init__(self) -> None:
        self.resources = {}

    async def list_resources(self, query):
        return list(self.resources.values())

    async def create_resource(self, payload):
        record = {"_id": ObjectId(), **payload}
        self.resources[str(record["_id"])] = record
        return record

    async def update_resource(self, resource_id, updates):
        record = self.resources.get(resource_id)
        if not record:
            return None
        record.update(updates)
        return record

    async def delete_resource(self, resource_id):
        return self.resources.get(resource_id)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.logs = [
            {
                "_id": ObjectId("507f1f77bcf86cd799439091"),
                "actorType": "user",
                "actorId": ObjectId("507f1f77bcf86cd799439012"),
                "sessionId": None,
                "action": "ADMIN_LOGIN",
                "resourceType": "auth",
                "resourceId": None,
                "ipHash": "present",
                "userAgentHash": "present",
                "createdAt": _now(),
            }
        ]

    async def list_audit_logs(self, query, limit):
        return self.logs[:limit]


def make_token(user_id: str, role: str) -> str:
    return build_auth_tokens(AuthenticatedUserPayload(userId=user_id, role=role)).access_token


@pytest.fixture
def admin_fakes(monkeypatch):
    auth_repo = FakeAuthRepository()
    admin_repo = FakeAdminRepository()
    content_repo = FakeContentRepository()
    platform_settings_repo = FakePlatformSettingsRepository()
    resources_repo = FakeResourcesRepository()
    audit_repo = FakeAuditRepository()

    async def noop_audit(*args, **kwargs):
        return None

    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    monkeypatch.setattr(admin_service_module, "get_admin_repository", lambda: admin_repo)
    monkeypatch.setattr(content_service_module, "get_content_repository", lambda: content_repo)
    monkeypatch.setattr(platform_settings_service_module, "get_platform_settings_repository", lambda: platform_settings_repo)
    monkeypatch.setattr(resources_service_module, "get_resources_repository", lambda: resources_repo)
    monkeypatch.setattr(audit_service_module, "get_audit_repository", lambda: audit_repo)
    monkeypatch.setattr(admin_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(content_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(platform_settings_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(resources_service_module, "create_audit_log", noop_audit)
    monkeypatch.setattr(audit_service_module, "create_audit_log", noop_audit)
    try:
        yield {
            "admin_repo": admin_repo,
            "content_repo": content_repo,
            "resources_repo": resources_repo,
        }
    finally:
        app.dependency_overrides.clear()


def test_admin_dashboard_and_user_update(admin_fakes):
    token = make_token("507f1f77bcf86cd799439012", "super_admin")
    managed_id = "507f1f77bcf86cd799439099"
    with TestClient(app) as client:
        dashboard = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
        users = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
        updated = client.patch(
            f"/api/v1/admin/users/{managed_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "inactive"},
        )
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["dashboard"]["users"] >= 1
    assert users.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["data"]["user"]["status"] == "inactive"


def test_admin_forbidden_for_public_user(admin_fakes):
    token = make_token("507f1f77bcf86cd799439011", "public_user")
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_content_platform_resources_and_audit_routes(admin_fakes):
    content_token = make_token("507f1f77bcf86cd799439014", "content_admin")
    super_admin_token = make_token("507f1f77bcf86cd799439012", "super_admin")
    with TestClient(app) as client:
        created_resource = client.post(
            "/api/v1/admin/content-resources",
            headers={"Authorization": f"Bearer {content_token}"},
            json={
                "name": "Know your rights",
                "language": "en",
                "category": "legal",
                "jurisdiction": "AU",
                "status": "published",
            },
        )
        resource_id = created_resource.json()["data"]["resource"]["id"]
        listed_resources = client.get(
            "/api/v1/admin/content-resources",
            headers={"Authorization": f"Bearer {content_token}"},
        )
        category = client.post(
            "/api/v1/admin/microeducation/categories",
            headers={"Authorization": f"Bearer {content_token}"},
            json={
                "name": "Safety",
                "backgroundColor": "#112233",
                "textColor": "#ffffff",
                "status": "published",
                "sortOrder": 1,
            },
        )
        item = client.post(
            "/api/v1/admin/microeducation",
            headers={"Authorization": f"Bearer {content_token}"},
            json={
                "title": "Stay safe",
                "summary": "Summary",
                "readTimeLabel": "2 min",
                "tag": "safe",
                "cta": "Open",
                "detailHeading": "Heading",
                "detailBody": "Body",
                "detailTakeaway": "Takeaway",
                "tone": "blue",
                "chips": ["safety"],
                "duration": "quick",
                "format": "guide",
                "status": "published",
                "sortOrder": 0,
                "views": 0,
            },
        )
        platform_settings = client.get(
            "/api/v1/admin/platform-settings",
            headers={"Authorization": f"Bearer {content_token}"},
        )
        published_platform_settings = client.post(
            "/api/v1/admin/platform-settings/publish",
            headers={"Authorization": f"Bearer {content_token}"},
        )
        created_library_resource = client.post(
            "/api/v1/admin/resources",
            headers={"Authorization": f"Bearer {content_token}"},
            json={"name": "Helpline", "category": "support", "status": "published", "sortOrder": 1},
        )
        audit_logs = client.get(
            "/api/v1/admin/audit-logs",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
    assert created_resource.status_code == 200
    assert listed_resources.status_code == 200
    assert listed_resources.json()["data"]["resources"][0]["id"] == resource_id
    assert category.status_code == 200
    assert item.status_code == 200
    assert platform_settings.status_code == 200
    assert published_platform_settings.status_code == 200
    assert created_library_resource.status_code == 200
    assert audit_logs.status_code == 200
    assert audit_logs.json()["data"]["auditLogs"][0]["ipHashPresent"] is True


def test_admin_destinations_templates_privacy_and_support(admin_fakes):
    integration_token = make_token("507f1f77bcf86cd799439016", "integration_admin")
    content_token = make_token("507f1f77bcf86cd799439014", "content_admin")
    super_admin_token = make_token("507f1f77bcf86cd799439012", "super_admin")
    with TestClient(app) as client:
        destination = client.post(
            "/api/v1/admin/destinations",
            headers={"Authorization": f"Bearer {integration_token}"},
            json={
                "type": "police",
                "key": "nsw-police",
                "name": "NSW Police",
                "channel": "manual_export_pdf",
                "jurisdiction": "NSW",
                "minimumRequiredInfo": [],
                "anonymityOptions": [],
                "expectedNextSteps": [],
            },
        )
        destination_id = destination.json()["data"]["destination"]["_id"]
        template = client.post(
            "/api/v1/admin/submission-templates",
            headers={"Authorization": f"Bearer {integration_token}"},
            json={
                "key": "police-template",
                "name": "Police Template",
                "destinationType": "police",
                "channel": "manual_export_pdf",
                "jurisdiction": "NSW",
                "titleTemplate": "Title",
                "summaryTemplate": "Summary",
                "acknowledgementMode": "manual",
                "attachmentMode": "metadata_only",
            },
        )
        support_service = client.post(
            "/api/v1/admin/support-services",
            headers={"Authorization": f"Bearer {content_token}"},
            json={
                "key": "svc-1",
                "name": "Support Line",
                "type": "counselling",
                "description": "Description",
                "resourceType": "mental_health",
                "ctaLabel": "Call",
                "jurisdiction": "AU",
            },
        )
        support_service_id = support_service.json()["data"]["service"]["_id"]
        privacy_request = client.patch(
            "/api/v1/admin/privacy-requests/507f1f77bcf86cd799439081",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"status": "completed"},
        )
        warm_referral = client.patch(
            "/api/v1/admin/support-services/warm-referrals/507f1f77bcf86cd799439086",
            headers={"Authorization": f"Bearer {content_token}"},
            json={"status": "accepted"},
        )
        support_service_update = client.patch(
            f"/api/v1/admin/support-services/{support_service_id}",
            headers={"Authorization": f"Bearer {content_token}"},
            json={"isActive": False},
        )
    assert destination.status_code == 200
    assert destination_id
    assert template.status_code == 200
    assert support_service.status_code == 200
    assert support_service_update.status_code == 200
    assert privacy_request.status_code == 200
    assert warm_referral.status_code == 200
