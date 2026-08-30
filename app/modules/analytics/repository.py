from typing import Any

from app.config.database import get_database


class AnalyticsRepository:
    def __init__(self) -> None:
        database = get_database()
        self.reports = database["reports"]

    async def list_reports(self, match: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self.reports.find(match)
        return await cursor.to_list(length=None)


def get_analytics_repository() -> AnalyticsRepository:
    return AnalyticsRepository()
