import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import nonebot
import pytest
from nonebot.adapters.onebot.v11 import Bot, Message

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

from nonebot_plugin_sublike import matcher, service
from nonebot_plugin_sublike.config import plugin_config
from nonebot_plugin_sublike.models import (
    LikeResult,
    LikeSource,
    LikeStatus,
    SubscriptionRecord,
    SubscriptionResult,
    SubscriptionStatus,
)
from tests.fake import fake_group_message_event_v11


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


def test_default_daily_like_commands():
    assert plugin_config.sublike_cmd_sub == ("每日赞", "天天赞我")
    assert plugin_config.sublike_cmd_unsub == ("取消每日赞", "每日赞取消")
    assert plugin_config.sublike_cmd_status == (
        "每日赞查看",
        "查看每日赞",
        "每日赞状态",
        "每日赞查询",
        "查询每日赞",
    )


def test_build_like_me_message_uses_daily_like_copy():
    assert (
        matcher.build_like_me_message(
            LikeResult(user_id=1, status=LikeStatus.NOT_FRIEND)
        )
        == "🙄 不加好友不赞"
    )
    assert (
        matcher.build_like_me_message(
            LikeResult(user_id=1, status=LikeStatus.SUCCESS, total=20)
        )
        == "👍 给你点了 20 个赞"
    )
    assert (
        matcher.build_like_me_message(
            LikeResult(user_id=1, status=LikeStatus.LIMIT_REACHED)
        )
        == "🌟 今天点满了，明天再来"
    )
    assert (
        matcher.build_like_me_message(LikeResult(user_id=1, status=LikeStatus.FAILED))
        == "💥 手滑了，没赞上"
    )


def test_build_like_other_message_uses_colloquial_copy():
    not_friend = cast(
        Message,
        matcher.build_like_other_message(
            582933105,
            LikeResult(user_id=582933105, status=LikeStatus.NOT_FRIEND),
        ),
    )
    assert [segment.type for segment in not_friend] == ["text", "at", "text"]
    assert not_friend[0].data["text"] == "🙄 先让 "
    assert not_friend[1].data["qq"] == "582933105"
    assert not_friend[2].data["text"] == " 加我好友，不然没法赞"

    success = cast(
        Message,
        matcher.build_like_other_message(
            582933105,
            LikeResult(
                user_id=582933105,
                status=LikeStatus.SUCCESS,
                total=30,
            ),
        ),
    )
    assert [segment.type for segment in success] == ["text", "at", "text"]
    assert success[0].data["text"] == "👍 已经帮你给 "
    assert success[1].data["qq"] == "582933105"
    assert success[2].data["text"] == " 点了 30 个赞"

    limit_reached = cast(
        Message,
        matcher.build_like_other_message(
            582933105,
            LikeResult(user_id=582933105, status=LikeStatus.LIMIT_REACHED),
        ),
    )
    assert [segment.type for segment in limit_reached] == ["text", "at", "text"]
    assert limit_reached[0].data["text"] == "🌟 今天给 "
    assert limit_reached[1].data["qq"] == "582933105"
    assert limit_reached[2].data["text"] == " 的赞已经点满了喵～"

    assert (
        matcher.build_like_other_message(
            582933105,
            LikeResult(user_id=582933105, status=LikeStatus.FAILED),
        )
        == "💥 手滑了，没赞上"
    )


@pytest.mark.asyncio
async def test_handle_like_other_without_target_uses_new_hint(
    monkeypatch: pytest.MonkeyPatch,
):
    event = fake_group_message_event_v11(
        message=Message("赞他"),
        raw_message="赞他",
    )
    captured: list[str] = []

    class StopHandling(Exception):
        pass

    async def fake_finish(message: str):
        captured.append(message)
        raise StopHandling

    monkeypatch.setattr(matcher.like_other, "finish", fake_finish)

    with pytest.raises(StopHandling):
        await matcher.handle_like_other(
            cast(Bot, cast(object, SimpleNamespace())),
            event,
        )

    assert captured == ["🤡 赞谁啊？直接说「赞他 QQ 号」或者「赞他 @群友」"]


def test_build_daily_like_messages(fixed_now: datetime):
    renewed_without_friend = matcher.build_subscribe_message(
        SubscriptionResult(
            user_id=582933105,
            status=SubscriptionStatus.RENEWED,
            require_friend=True,
            is_friend=False,
        )
    )
    assert renewed_without_friend == "🔁 每日赞给你续上了，没加好友可能点不上"

    renewed = matcher.build_subscribe_message(
        SubscriptionResult(
            user_id=582933105,
            status=SubscriptionStatus.RENEWED,
        )
    )
    assert renewed == "🔁 每日赞给你续上了"

    subscribed_without_friend = matcher.build_subscribe_message(
        SubscriptionResult(
            user_id=582933105,
            status=SubscriptionStatus.SUBSCRIBED,
            require_friend=True,
            is_friend=False,
        )
    )
    assert subscribed_without_friend == "👍 每日赞给你开好了，没加好友可能点不上"

    subscribed = matcher.build_subscribe_message(
        SubscriptionResult(
            user_id=582933105,
            status=SubscriptionStatus.SUBSCRIBED,
        )
    )
    assert subscribed == "👍 每日赞给你开好了"

    failed = matcher.build_subscribe_message(
        SubscriptionResult(
            user_id=582933105,
            status=SubscriptionStatus.NOT_SUBSCRIBED,
        )
    )
    assert failed == "💥 失败了喵～请稍后再试"

    assert (
        matcher.build_unsubscribe_message(
            SubscriptionResult(
                user_id=582933105,
                status=SubscriptionStatus.UNSUBSCRIBED,
            )
        )
        == "👌 每日赞给你关了"
    )
    assert (
        matcher.build_unsubscribe_message(
            SubscriptionResult(
                user_id=582933105,
                status=SubscriptionStatus.NOT_SUBSCRIBED,
            )
        )
        == "💢 你这边本来就没开每日赞"
    )

    assert (
        matcher.build_status_message(
            SubscriptionResult(
                user_id=582933105,
                status=SubscriptionStatus.EMPTY,
                is_superuser_view=True,
            )
        )
        == "📭 现在没人开着每日赞"
    )
    assert (
        matcher.build_status_message(
            SubscriptionResult(
                user_id=582933105,
                status=SubscriptionStatus.EMPTY,
            )
        )
        == "📭 你这边还没开每日赞"
    )

    list_record = SubscriptionRecord(
        user_id=582933105,
        created_at=fixed_now,
        last_trigger_at=fixed_now,
        expires_at=fixed_now + timedelta(days=7),
    )
    assert (
        matcher.build_status_message(
            SubscriptionResult(
                user_id=1,
                status=SubscriptionStatus.STATUS_LIST,
                records=[list_record],
            )
        )
        == "📋 天天赞列表：\n582933105 到期：2026-04-15"
    )

    single_record = SubscriptionRecord(
        user_id=582933105,
        created_at=fixed_now,
        last_trigger_at=fixed_now,
        expires_at=fixed_now + timedelta(days=7),
        last_like_at=fixed_now - timedelta(days=1),
    )
    assert matcher.build_status_message(
        SubscriptionResult(
            user_id=582933105,
            status=SubscriptionStatus.STATUS_SINGLE,
            record=single_record,
        )
    ) == "\n".join(
        [
            "📌 你的每日赞情况：",
            "QQ：582933105",
            "到期：2026-04-15",
            "上次点赞：2026-04-07",
        ]
    )

    no_like_record = SubscriptionRecord(
        user_id=582933105,
        created_at=fixed_now,
        last_trigger_at=fixed_now,
        expires_at=fixed_now + timedelta(days=7),
    )
    assert matcher.build_status_message(
        SubscriptionResult(
            user_id=582933105,
            status=SubscriptionStatus.STATUS_SINGLE,
            record=no_like_record,
        )
    ) == "\n".join(
        [
            "📌 你的每日赞情况：",
            "QQ：582933105",
            "到期：2026-04-15",
            "上次点赞：还没有",
        ]
    )

    assert (
        matcher.build_status_message(
            SubscriptionResult(
                user_id=582933105,
                status=SubscriptionStatus.NOT_SUBSCRIBED,
            )
        )
        == "💥 我这边没查到，你再试一次"
    )
