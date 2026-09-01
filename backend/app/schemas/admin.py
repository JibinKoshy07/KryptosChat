"""Admin dashboard schemas."""
from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    online_users: int
    total_conversations: int
    total_messages: int
    storage_usage_bytes: int
    recent_signups: list[dict]
    recent_activity: list[dict]