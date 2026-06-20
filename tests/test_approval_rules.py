from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.services import knowledge


@pytest.mark.asyncio
async def test_unreviewed_legal_source_cannot_be_approved(monkeypatch):
    async def fake_source(_source_id: str):
        return {
            "sourceCategory": "official_legal_source",
            "legalReviewed": False,
            "ingestionStatus": "embedded",
            "nextRefreshAt": datetime.now(UTC) + timedelta(days=30),
        }

    monkeypatch.setattr(knowledge, "get_source", fake_source)

    with pytest.raises(HTTPException) as error:
        await knowledge.set_approval("a" * 24, "b" * 24, True)

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_naive_legacy_refresh_datetime_is_compared_as_utc(monkeypatch):
    async def fake_source(_source_id: str):
        return {
            "sourceCategory": "official_support_source",
            "legalReviewed": True,
            "ingestionStatus": "embedded",
            "nextRefreshAt": datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
        }

    monkeypatch.setattr(knowledge, "get_source", fake_source)

    with pytest.raises(HTTPException) as error:
        await knowledge.set_approval("a" * 24, "b" * 24, True)

    assert error.value.status_code == 409
    assert error.value.detail == "Knowledge source refresh is expired"
