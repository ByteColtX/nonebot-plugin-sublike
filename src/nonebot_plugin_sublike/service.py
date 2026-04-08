"""点赞业务逻辑。"""

import asyncio
from datetime import datetime, timedelta

from nonebot import get_driver, logger
from nonebot.adapters.onebot.v11 import Bot

from .config import plugin_config
from .models import (
    LikeResult,
    LikeSource,
    LikeStatus,
    SubscriptionRecord,
    SubscriptionResult,
    SubscriptionStatus,
    UserLikeStats,
)
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


async def check_friend(
    bot: Bot,
    user_id: int,
    *,
    require_friend: bool,
) -> bool:
    """按配置判断是否需要好友关系。"""

    if not require_friend:
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


def _is_limit_response(response: object) -> bool:
    """判断接口返回是否表示已到点赞上限。"""

    if not isinstance(response, dict):
        return False

    return response.get("ok") is False or response.get("times") == 0


def _is_limit_exception(exception: Exception) -> bool:
    """判断异常是否表示已到点赞上限。"""

    text = repr(exception)
    limit_markers = (
        "已达上限",
        "不能再赞",
        "点赞失败 今日同一好友点赞数已达上限",
        "limit",
    )
    return any(marker in text for marker in limit_markers)


async def execute_like(bot: Bot, user_id: int, *, source: LikeSource) -> LikeResult:
    """执行点赞请求，直到接口拒绝继续点赞为止。"""

    result = LikeResult(
        user_id=user_id,
        source=source,
        status=LikeStatus.FAILED,
    )
    while True:
        try:
            response = await bot.send_like(user_id=user_id, times=10)
        except Exception as exception:
            if result.total > 0:
                result.success = True
                result.status = LikeStatus.SUCCESS
                result.hit_limit = True
                result.detail = repr(exception)
                logger.info(
                    f"用户 {user_id} 点赞已到上限，本次累计 {result.total} 赞："
                    f"{exception!r}"
                )
            elif _is_limit_exception(exception):
                result.status = LikeStatus.LIMIT_REACHED
                result.hit_limit = True
                result.detail = repr(exception)
                logger.info(f"用户 {user_id} 今日点赞已达上限：{exception!r}")
            else:
                result.status = LikeStatus.FAILED
                result.detail = repr(exception)
                logger.warning(f"用户 {user_id} 点赞失败：{exception!r}")
            break

        result.total += 10

        if _is_limit_response(response):
            result.hit_limit = True
            break

    if result.total > 0:
        result.success = True
        result.status = LikeStatus.SUCCESS

    return result


async def handle_instant_like(
    bot: Bot,
    user_id: int,
    *,
    source: LikeSource = LikeSource.INSTANT,
) -> LikeResult:
    """处理即时点赞流程。"""

    result = LikeResult(user_id=user_id, source=source)
    result.is_friend = await check_friend(
        bot,
        user_id,
        require_friend=plugin_config.sublike_need_friend_me,
    )
    if not result.is_friend:
        result.status = LikeStatus.NOT_FRIEND
        return result

    like_result = await execute_like(bot, user_id, source=source)
    like_result.is_friend = result.is_friend

    if like_result.success:
        update_user_like_stats(user_id, like_result.total, datetime.now())

    return like_result


def _get_superusers() -> set[str]:
    """获取超级用户列表。"""

    return set(get_driver().config.superusers)


async def handle_subscribe(bot: Bot, user_id: int) -> SubscriptionResult:
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

    require_friend = plugin_config.sublike_need_friend_sub
    friend_state: bool | None = None
    if require_friend:
        friend_state = await is_friend(bot, user_id)

    return SubscriptionResult(
        user_id=user_id,
        status=(
            SubscriptionStatus.RENEWED if is_renew else SubscriptionStatus.SUBSCRIBED
        ),
        require_friend=require_friend,
        is_friend=friend_state,
        record=record,
    )


def handle_unsubscribe(user_id: int) -> SubscriptionResult:
    """取消订阅。"""

    removed = remove_subscription(user_id)
    if removed:
        return SubscriptionResult(
            user_id=user_id,
            status=SubscriptionStatus.UNSUBSCRIBED,
        )
    return SubscriptionResult(
        user_id=user_id,
        status=SubscriptionStatus.NOT_SUBSCRIBED,
    )


def handle_subscription_status(
    user_id: int,
    is_superuser: bool,
) -> SubscriptionResult:
    """查看订阅状态。"""

    now = datetime.now()
    purge_expired_subscriptions(now)

    if is_superuser:
        records = load_subscriptions()
        if not records:
            return SubscriptionResult(
                user_id=user_id,
                status=SubscriptionStatus.EMPTY,
                is_superuser_view=True,
            )
        return SubscriptionResult(
            user_id=user_id,
            status=SubscriptionStatus.STATUS_LIST,
            is_superuser_view=True,
            records=records,
        )

    record = get_subscription(user_id)
    if record is None or record.expires_at <= now:
        return SubscriptionResult(
            user_id=user_id,
            status=SubscriptionStatus.EMPTY,
        )

    return SubscriptionResult(
        user_id=user_id,
        status=SubscriptionStatus.STATUS_SINGLE,
        record=record,
    )


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
        result.is_friend = await check_friend(
            bot,
            record.user_id,
            require_friend=plugin_config.sublike_need_friend_sub,
        )
        if not result.is_friend:
            result.status = LikeStatus.NOT_FRIEND
            result.detail = "当前不是机器人好友，跳过订阅点赞"
            return result

    delay_seconds = get_random_delay_seconds(plugin_config.sublike_delay_max)
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)

    result = await execute_like(
        bot,
        record.user_id,
        source=LikeSource.SUBSCRIPTION,
    )
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
        result = await handle_subscription_like(bot, record)
        if result.status == LikeStatus.NOT_FRIEND:
            logger.info(f"用户 {record.user_id} 不是好友，跳过订阅点赞")
        elif result.status == LikeStatus.FAILED:
            logger.warning(f"用户 {record.user_id} 订阅点赞失败：{result.detail}")
