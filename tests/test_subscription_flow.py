import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import nonebot
import pytest
from nonebot.adapters.onebot.v11 import Bot

nonebot.init(driver="~none")
nonebot.require = lambda name: ModuleType(name)

fake_localstore = ModuleType("nonebot_plugin_localstore")
cast(Any, fake_localstore).get_plugin_data_file = lambda name: Path("/tmp") / name
sys.modules["nonebot_plugin_localstore"] = fake_localstore

fake_scheduler = ModuleType("nonebot_plugin_apscheduler")


class _FakeScheduler:
    def scheduled_job(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


cast(Any, fake_scheduler).scheduler = _FakeScheduler()
sys.modules["nonebot_plugin_apscheduler"] = fake_scheduler

from nonebot_plugin_sublike import service
from nonebot_plugin_sublike.models import (
    LikeResult,
    LikeSource,
    LikeStatus,
    SubscriptionRecord,
    SubscriptionStatus,
)


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 4, 8, 12, 0, 0, tzinfo=tz)


@pytest.fixture()
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    now = FixedDateTime.now()
    monkeypatch.setattr(service, "datetime", FixedDateTime)
    return now


@pytest.fixture()
def subscription_store(monkeypatch: pytest.MonkeyPatch):
    records: dict[int, SubscriptionRecord] = {}

    def get_subscription(user_id: int):
        return records.get(user_id)

    def upsert_subscription(record: SubscriptionRecord):
        records[record.user_id] = record

    def remove_subscription(user_id: int):
        return records.pop(user_id, None) is not None

    def load_subscriptions():
        return sorted(records.values(), key=lambda record: record.user_id)

    def purge_expired_subscriptions(now: datetime):
        expired_ids = [
            user_id for user_id, record in records.items() if record.expires_at <= now
        ]
        for user_id in expired_ids:
            records.pop(user_id)
        return len(expired_ids)

    monkeypatch.setattr(service, "get_subscription", get_subscription)
    monkeypatch.setattr(service, "upsert_subscription", upsert_subscription)
    monkeypatch.setattr(service, "remove_subscription", remove_subscription)
    monkeypatch.setattr(service, "load_subscriptions", load_subscriptions)
    monkeypatch.setattr(
        service,
        "purge_expired_subscriptions",
        purge_expired_subscriptions,
    )
    return records


@pytest.fixture()
def configured_subscription_flow(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service.plugin_config, "sublike_sub_expire_days", 7)
    monkeypatch.setattr(service.plugin_config, "sublike_need_friend_sub", False)

    async def fake_subscription_like(
        bot,
        record,
        *,
        skip_delay=False,
        friend_state=None,
    ):
        return LikeResult(
            user_id=record.user_id,
            source=LikeSource.SUBSCRIPTION,
            status=LikeStatus.SUCCESS,
            total=10,
            success=True,
            is_friend=friend_state,
        )

    monkeypatch.setattr(service, "handle_subscription_like", fake_subscription_like)


@pytest.mark.asyncio
async def test_handle_subscribe_creates_new_subscription(
    fixed_now: datetime,
    subscription_store,
    configured_subscription_flow,
):
    result = await service.handle_subscribe(
        cast(Bot, cast(object, SimpleNamespace())),
        582933105,
    )

    assert result.status == SubscriptionStatus.SUBSCRIBED
    assert result.record is not None
    assert result.record.user_id == 582933105
    assert result.record.created_at == fixed_now
    assert result.record.last_trigger_at == fixed_now
    assert result.record.expires_at == fixed_now + timedelta(days=7)
    assert subscription_store[582933105].expires_at == fixed_now + timedelta(days=7)


@pytest.mark.asyncio
async def test_handle_subscribe_renews_existing_subscription(
    fixed_now: datetime,
    subscription_store,
    configured_subscription_flow,
):
    original = SubscriptionRecord(
        user_id=582933105,
        created_at=fixed_now - timedelta(days=3),
        last_trigger_at=fixed_now - timedelta(days=1),
        expires_at=fixed_now + timedelta(days=1),
    )
    subscription_store[582933105] = original

    result = await service.handle_subscribe(
        cast(Bot, cast(object, SimpleNamespace())),
        582933105,
    )

    assert result.status == SubscriptionStatus.RENEWED
    assert result.record is not None
    assert result.record.created_at == original.created_at
    assert result.record.last_trigger_at == fixed_now
    assert result.record.expires_at == fixed_now + timedelta(days=7)


def test_handle_unsubscribe_returns_expected_status(subscription_store):
    subscription_store[582933105] = SubscriptionRecord(
        user_id=582933105,
        created_at=datetime(2026, 4, 1, 8, 0, 0),
        last_trigger_at=datetime(2026, 4, 1, 8, 0, 0),
        expires_at=datetime(2026, 4, 15, 8, 0, 0),
    )

    removed = service.handle_unsubscribe(582933105)
    missing = service.handle_unsubscribe(582933105)

    assert removed.status == SubscriptionStatus.UNSUBSCRIBED
    assert missing.status == SubscriptionStatus.NOT_SUBSCRIBED


def test_handle_subscription_status_for_user_and_superuser(
    fixed_now: datetime,
    subscription_store,
):
    valid_record = SubscriptionRecord(
        user_id=582933105,
        created_at=fixed_now - timedelta(days=1),
        last_trigger_at=fixed_now - timedelta(hours=1),
        expires_at=fixed_now + timedelta(days=6),
    )
    expired_record = SubscriptionRecord(
        user_id=424155717,
        created_at=fixed_now - timedelta(days=8),
        last_trigger_at=fixed_now - timedelta(days=7),
        expires_at=fixed_now - timedelta(seconds=1),
    )
    subscription_store[valid_record.user_id] = valid_record
    subscription_store[expired_record.user_id] = expired_record

    user_result = service.handle_subscription_status(582933105, is_superuser=False)
    empty_result = service.handle_subscription_status(1208830145, is_superuser=False)
    superuser_result = service.handle_subscription_status(1, is_superuser=True)

    assert user_result.status == SubscriptionStatus.STATUS_SINGLE
    assert user_result.record is not None
    assert user_result.record.user_id == 582933105

    assert empty_result.status == SubscriptionStatus.EMPTY

    assert superuser_result.status == SubscriptionStatus.STATUS_LIST
    assert superuser_result.is_superuser_view is True
    assert [record.user_id for record in superuser_result.records] == [582933105]
