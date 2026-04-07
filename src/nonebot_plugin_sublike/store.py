"""数据存储。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from nonebot import require
from pydantic import BaseModel

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from .models import SubscriptionRecord, UserLikeStats

SUBSCRIPTIONS_FILE = store.get_plugin_data_file("subscriptions.json")
USER_STATS_FILE = store.get_plugin_data_file("user_stats.json")
ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_records(
    file_path: Path,
    model_type: type[SubscriptionRecord],
) -> list[SubscriptionRecord]:
    """读取订阅记录列表。"""

    return _load_model_list(file_path, model_type)


def _load_stats(
    file_path: Path,
    model_type: type[UserLikeStats],
) -> list[UserLikeStats]:
    """读取用户统计列表。"""

    return _load_model_list(file_path, model_type)


def _load_model_list(
    file_path: Path,
    model_type: type[ModelT],
) -> list[ModelT]:
    """从 JSON 文件中读取模型列表。"""

    if not file_path.exists():
        return []

    try:
        raw_data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(raw_data, list):
        return []

    records: list[ModelT] = []
    for item in raw_data:
        try:
            records.append(model_type.model_validate(item))
        except Exception:
            continue

    return records


def _save_model_list(
    file_path: Path,
    records: list[SubscriptionRecord] | list[UserLikeStats],
) -> None:
    """将模型列表写入 JSON 文件。"""

    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.model_dump(mode="json") for record in records]
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_subscriptions() -> list[SubscriptionRecord]:
    """读取全部订阅记录。"""

    records = _load_records(SUBSCRIPTIONS_FILE, SubscriptionRecord)
    return sorted(records, key=lambda record: record.user_id)


def save_subscriptions(records: list[SubscriptionRecord]) -> None:
    """保存全部订阅记录。"""

    ordered_records = sorted(records, key=lambda record: record.user_id)
    _save_model_list(SUBSCRIPTIONS_FILE, ordered_records)


def get_subscription(user_id: int) -> SubscriptionRecord | None:
    """按 QQ 号获取订阅记录。"""

    for record in load_subscriptions():
        if record.user_id == user_id:
            return record
    return None


def upsert_subscription(record: SubscriptionRecord) -> None:
    """新增或更新订阅记录。"""

    records = [item for item in load_subscriptions() if item.user_id != record.user_id]
    records.append(record)
    save_subscriptions(records)


def remove_subscription(user_id: int) -> bool:
    """删除订阅记录。"""

    records = load_subscriptions()
    new_records = [record for record in records if record.user_id != user_id]
    if len(new_records) == len(records):
        return False

    save_subscriptions(new_records)
    return True


def purge_expired_subscriptions(now: datetime) -> int:
    """清理已过期的订阅记录。"""

    records = load_subscriptions()
    valid_records = [record for record in records if record.expires_at > now]
    removed_count = len(records) - len(valid_records)
    if removed_count > 0:
        save_subscriptions(valid_records)
    return removed_count


def load_user_stats() -> list[UserLikeStats]:
    """读取全部用户统计。"""

    records = _load_stats(USER_STATS_FILE, UserLikeStats)
    return sorted(records, key=lambda record: record.user_id)


def save_user_stats(records: list[UserLikeStats]) -> None:
    """保存全部用户统计。"""

    ordered_records = sorted(records, key=lambda record: record.user_id)
    _save_model_list(USER_STATS_FILE, ordered_records)


def get_user_stats(user_id: int) -> UserLikeStats | None:
    """按 QQ 号获取用户统计。"""

    for record in load_user_stats():
        if record.user_id == user_id:
            return record
    return None


def upsert_user_stats(record: UserLikeStats) -> None:
    """新增或更新用户统计。"""

    records = [item for item in load_user_stats() if item.user_id != record.user_id]
    records.append(record)
    save_user_stats(records)
