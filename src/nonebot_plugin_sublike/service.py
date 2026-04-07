"""点赞业务逻辑。"""

import asyncio
from datetime import datetime, timedelta

from nonebot import get_driver
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot

from .config import plugin_config
from .models import LikeResult, LikeSource, SubscriptionRecord, UserLikeStats
from .store import (
    get_subscription,
    get_user_stats,
    load_subscriptions,
    purge_expired_subscriptions,
    remove_subscription,
    upsert_subscription,
    upsert_user_stats,
)
from .utils import get_random_delay_seconds, in_active_window, is_friend


async def check_instant_like_friend(bot: Bot, user_id: int) -> bool:
    """按配置判断即时点赞是否需要好友关系。"""

    if not plugin_config.sublike_need_friend_me:
        return True

    return await is_friend(bot, user_id)


def update_user_like_stats(user_id: int, total: int, liked_at: datetime) -> None:
    """更新用户累计点赞统计。"""

    stats = get_user_stats(user_id)
    if stats is None:
        stats = UserLikeStats(user_id=user_id)

    liked_date = liked_at.date()
    if stats.last_like_date != liked_date:
        stats.total_like_days += 1

    stats.total_like_count += total
    stats.last_like_date = liked_date
    upsert_user_stats(stats)


async def send_like_until_limit(bot: Bot, user_id: int) -> LikeResult:
    """持续点赞，直到接口拒绝继续点赞为止。"""

    result = LikeResult(user_id=user_id)
    like_times = plugin_config.sublike_like_times

    while True:
        try:
            response = await bot.send_like(user_id=user_id, times=like_times)
        except Exception as exception:
            result.hit_limit = True
            if result.total > 0:
                result.success = True
                result.message = f"👍 已经点了 {result.total} 个赞"
                logger.info(
                    f"用户 {user_id} 点赞已到上限，本次累计 {result.total} 赞："
                    f"{exception!r}"
                )
            else:
                result.message = "🌟 今天赞不了更多了喵~"
                logger.warning(f"用户 {user_id} 点赞失败：{exception!r}")
            break

        result.total += like_times

        if isinstance(response, dict):
            if response.get("ok") is False or response.get("times") == 0:
                result.hit_limit = True
                break

    if result.total > 0:
        result.success = True
        result.message = f"👍 已经点了 {result.total} 个赞"

    return result


async def handle_instant_like(
    bot: Bot,
    user_id: int,
    *,
    source: LikeSource = LikeSource.INSTANT,
) -> LikeResult:
    """处理即时点赞流程，并在成功后更新累计统计。"""

    result = LikeResult(user_id=user_id, source=source)
    result.is_friend = await check_instant_like_friend(bot, user_id)
    if not result.is_friend:
        result.message = "⚠️ 需要先加好友才能点赞"
        return result

    like_result = await send_like_until_limit(bot, user_id)
    like_result.source = source
    like_result.is_friend = result.is_friend

    if like_result.success:
        update_user_like_stats(user_id, like_result.total, datetime.now())

    return like_result


def _get_superusers() -> set[str]:
    """获取超级用户列表。"""

    return set(get_driver().config.superusers)


async def handle_subscribe(bot: Bot, user_id: int) -> str:
    """创建或续期订阅。"""

    now = datetime.now()
    purge_expired_subscriptions(now)

    current = get_subscription(user_id)
    expires_at = now + timedelta(days=plugin_config.sublike_sub_expire_days)
    is_renew = current is not None and current.expires_at > now

    if current is None or current.expires_at <= now:
        record = SubscriptionRecord(
            user_id=user_id,
            created_at=now,
            last_trigger_at=now,
            expires_at=expires_at,
        )
    else:
        record = current.model_copy(
            update={
                "last_trigger_at": now,
                "expires_at": expires_at,
            }
        )

    upsert_subscription(record)

    if plugin_config.sublike_need_friend_sub and not await is_friend(bot, user_id):
        if is_renew:
            return (
                "🔁 订阅赞已续期，但当前你还不是机器人好友，"
                "定时点赞可能不会生效"
            )
        return "👍 订阅赞成功，但当前你还不是机器人好友，定时点赞可能不会生效"

    if is_renew:
        return "🔁 订阅赞已续期"
    return "👍 订阅赞成功"


def handle_unsubscribe(user_id: int) -> str:
    """取消订阅。"""

    removed = remove_subscription(user_id)
    if removed:
        return "👎 已取消订阅赞"
    return "💢 你当前没有订阅赞"


def handle_subscription_status(user_id: int, is_superuser: bool) -> str:
    """查看订阅状态。"""

    now = datetime.now()
    purge_expired_subscriptions(now)

    if is_superuser:
        records = load_subscriptions()
        if not records:
            return "📭 当前没有有效订阅"

        lines = ["📋 当前有效订阅："]
        for record in records:
            lines.append(
                f"{record.user_id} 到期于 {record.expires_at:%Y-%m-%d %H:%M:%S}"
            )
        return "\n".join(lines)

    record = get_subscription(user_id)
    if record is None or record.expires_at <= now:
        return "📭 你当前没有有效订阅"

    lines = [
        "📌 你的订阅状态：",
        f"QQ：{record.user_id}",
        f"到期时间：{record.expires_at:%Y-%m-%d %H:%M:%S}",
    ]
    if record.last_like_at is not None:
        lines.append(f"最近点赞：{record.last_like_at:%Y-%m-%d %H:%M:%S}")
    else:
        lines.append("最近点赞：暂无")

    return "\n".join(lines)


def is_superuser(user_id: int) -> bool:
    """判断当前用户是否为超级用户。"""

    return str(user_id) in _get_superusers()


async def handle_subscription_like(bot: Bot, record: SubscriptionRecord) -> LikeResult:
    """执行单个订阅用户的定时点赞。"""

    result = LikeResult(
        user_id=record.user_id,
        source=LikeSource.SUBSCRIPTION,
    )

    if plugin_config.sublike_need_friend_sub:
        result.is_friend = await is_friend(bot, record.user_id)
        if not result.is_friend:
            result.message = "⚠️ 当前不是机器人好友，跳过订阅点赞"
            return result

    delay_seconds = get_random_delay_seconds(plugin_config.sublike_delay_max)
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)

    result = await send_like_until_limit(bot, record.user_id)
    result.source = LikeSource.SUBSCRIPTION
    if plugin_config.sublike_need_friend_sub:
        result.is_friend = True

    if result.success:
        now = datetime.now()
        update_user_like_stats(record.user_id, result.total, now)
        updated_record = record.model_copy(
            update={
                "last_like_at": now,
                "last_like_date": now.date(),
            }
        )
        upsert_subscription(updated_record)

    return result


async def run_subscription_scan(bot: Bot) -> None:
    """执行一次订阅扫描。"""

    now = datetime.now()
    if not in_active_window(
        now,
        plugin_config.sublike_sched_start,
        plugin_config.sublike_sched_end,
    ):
        return

    purge_expired_subscriptions(now)
    records = load_subscriptions()
    for record in records:
        if record.last_like_date == now.date():
            continue
        await handle_subscription_like(bot, record)
