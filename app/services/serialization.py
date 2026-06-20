from datetime import date, datetime
from typing import Any

from bson import ObjectId


def json_safe(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        result = {key: json_safe(item) for key, item in value.items()}
        if "_id" in result:
            result.setdefault("id", result["_id"])
        return result
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value

