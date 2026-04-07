"""数据模型。"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class LikeSource(str, Enum):
    """点赞来源。"""

    INSTANT = "instant"
    SUBSCRIPTION = "subscription"


class SubscriptionRecord(BaseModel):
    """订阅记录。"""

    user_id: int
    created_at: datetime
    last_trigger_at: datetime
    expires_at: datetime
    last_like_at: datetime | None = None
    last_like_date: date | None = None


class UserLikeStats(BaseModel):
    """用户累计点赞统计。"""

    user_id: int
    total_like_days: int = Field(default=0, ge=0)
    total_like_count: int = Field(default=0, ge=0)
    last_like_date: date | None = None


class LikeResult(BaseModel):
    """单次点赞流程结果。"""

    user_id: int
    total: int = Field(default=0, ge=0)
    source: LikeSource = LikeSource.INSTANT
    is_friend: bool | None = None
    hit_limit: bool = False
    success: bool = False
    message: str = ""
