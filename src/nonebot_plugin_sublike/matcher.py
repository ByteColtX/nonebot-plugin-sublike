"""消息触发器。"""

import re

from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.rule import Rule

from .config import plugin_config
from .models import (
    LikeResult,
    LikeSource,
    LikeStatus,
    SubscriptionResult,
    SubscriptionStatus,
)
from .service import (
    handle_instant_like,
    handle_subscribe,
    handle_subscription_status,
    handle_unsubscribe,
    is_superuser,
)

QQ_RE = re.compile(r"\b[1-9]\d{5,11}\b")


def _is_banned_group(event: MessageEvent) -> bool:
    """判断当前消息是否来自被禁用的群。"""

    return (
        isinstance(event, GroupMessageEvent)
        and event.group_id in plugin_config.sublike_banned_groups
    )


def is_like_me(event: MessageEvent) -> bool:
    """判断消息是否为“赞我”命令。"""

    if _is_banned_group(event):
        return False

    plain_text = event.get_plaintext().strip()
    return plain_text in plugin_config.sublike_cmd_me


def is_like_other(event: MessageEvent) -> bool:
    """判断消息是否为“赞他人”命令。"""

    if not plugin_config.sublike_allow_other:
        return False
    if not isinstance(event, GroupMessageEvent):
        return False
    if _is_banned_group(event):
        return False

    plain_text = event.get_plaintext().strip()
    return any(
        plain_text.startswith(keyword) for keyword in plugin_config.sublike_cmd_other
    )


def is_subscribe(event: MessageEvent) -> bool:
    """判断消息是否为订阅命令。"""

    if _is_banned_group(event):
        return False

    plain_text = event.get_plaintext().strip()
    return plain_text in plugin_config.sublike_cmd_sub


def is_unsubscribe(event: MessageEvent) -> bool:
    """判断消息是否为取消订阅命令。"""

    if _is_banned_group(event):
        return False

    plain_text = event.get_plaintext().strip()
    return plain_text in plugin_config.sublike_cmd_unsub


def is_subscription_status(event: MessageEvent) -> bool:
    """判断消息是否为订阅状态查询命令。"""

    if _is_banned_group(event):
        return False

    plain_text = event.get_plaintext().strip()
    return plain_text in plugin_config.sublike_cmd_status


def extract_target_user_id(event: GroupMessageEvent) -> int | None:
    """从群消息中提取被点赞的目标 QQ 号。"""

    for segment in event.get_message():
        if segment.type != "at":
            continue
        qq = segment.data.get("qq")
        if isinstance(qq, str) and qq.isdigit():
            return int(qq)

    plain_text = event.get_plaintext().strip()
    match = QQ_RE.search(plain_text)
    if match is None:
        return None

    return int(match.group(0))


def build_like_me_message(result: LikeResult) -> str:
    """生成“赞我”回复文案。"""

    if result.status == LikeStatus.NOT_FRIEND:
        return "🙄 不加好友不赞"
    if result.status == LikeStatus.SUCCESS:
        return f"👍 给你点了 {result.total} 个赞"
    if result.status == LikeStatus.LIMIT_REACHED:
        return "🌟 今天点满了，明天再来"
    return "💥 手滑了，没赞上"


def build_like_other_message(
    target_user_id: int,
    result: LikeResult,
) -> Message | str:
    """生成“赞他”回复文案。"""

    if result.status == LikeStatus.NOT_FRIEND:
        return Message(
            [
                MessageSegment.text("🙄 先让 "),
                MessageSegment.at(target_user_id),
                MessageSegment.text(" 加我好友，不然没法赞"),
            ]
        )

    if result.status == LikeStatus.SUCCESS:
        return Message(
            [
                MessageSegment.text("👍 已经帮你给 "),
                MessageSegment.at(target_user_id),
                MessageSegment.text(f" 点了 {result.total} 个赞"),
            ]
        )

    if result.status == LikeStatus.LIMIT_REACHED:
        return Message(
            [
                MessageSegment.text("🌟 今天给 "),
                MessageSegment.at(target_user_id),
                MessageSegment.text(" 的赞已经点满了喵～"),
            ]
        )

    return "💥 手滑了，没赞上"


def build_subscribe_message(result: SubscriptionResult) -> str:
    """生成订阅命令回复文案。"""

    if result.status == SubscriptionStatus.RENEWED:
        if result.require_friend and result.is_friend is False:
            return "🔁 每日赞给你续上了，没加好友可能点不上"
        return "🔁 每日赞给你续上了"

    if result.status == SubscriptionStatus.SUBSCRIBED:
        if result.require_friend and result.is_friend is False:
            return "👍 每日赞给你开好了，没加好友可能点不上"
        return "👍 每日赞给你开好了"

    return "💥 失败了喵～请稍后再试"


def build_unsubscribe_message(result: SubscriptionResult) -> str:
    """生成取消订阅回复文案。"""

    if result.status == SubscriptionStatus.UNSUBSCRIBED:
        return "👌 每日赞给你关了"
    return "💢 你这边本来就没开每日赞"


def build_status_message(result: SubscriptionResult) -> str:
    """生成订阅状态回复文案。"""

    if result.status == SubscriptionStatus.EMPTY:
        if result.is_superuser_view:
            return "📭 现在没人开着每日赞"
        return "📭 你这边还没开每日赞"

    if result.status == SubscriptionStatus.STATUS_LIST:
        lines = ["📋 天天赞列表："]
        for record in result.records:
            lines.append(f"{record.user_id} 到期：{record.expires_at:%Y-%m-%d}")
        return "\n".join(lines)

    if result.status == SubscriptionStatus.STATUS_SINGLE and result.record is not None:
        lines = [
            "📌 你的每日赞情况：",
            f"QQ：{result.record.user_id}",
            f"到期：{result.record.expires_at:%Y-%m-%d}",
        ]
        if result.record.last_like_at is not None:
            lines.append(f"上次点赞：{result.record.last_like_at:%Y-%m-%d}")
        else:
            lines.append("上次点赞：还没有")
        return "\n".join(lines)

    return "💥 我这边没查到，你再试一次"


like_me = on_message(rule=Rule(is_like_me), priority=5, block=True)
like_other = on_message(rule=Rule(is_like_other), priority=5, block=True)
like_subscribe = on_message(rule=Rule(is_subscribe), priority=5, block=True)
like_unsubscribe = on_message(rule=Rule(is_unsubscribe), priority=5, block=True)
like_status = on_message(
    rule=Rule(is_subscription_status),
    priority=5,
    block=True,
)


@like_me.handle()
async def handle_like_me(bot: Bot, event: MessageEvent):
    """处理“赞我”命令。"""

    result = await handle_instant_like(bot, event.user_id)
    await like_me.finish(build_like_me_message(result))


@like_other.handle()
async def handle_like_other(bot: Bot, event: GroupMessageEvent):
    """处理“赞他人”命令。"""

    target_user_id = extract_target_user_id(event)
    if target_user_id is None:
        await like_other.finish("🤡 赞谁啊？直接说「赞他 QQ 号」或者「赞他 @群友」")

    result = await handle_instant_like(
        bot,
        target_user_id,
        source=LikeSource.INSTANT,
    )
    reply = build_like_other_message(target_user_id, result)
    await like_other.finish(reply)


@like_subscribe.handle()
async def handle_like_subscribe(bot: Bot, event: MessageEvent):
    """处理订阅命令。"""

    result = await handle_subscribe(bot, event.user_id)
    await like_subscribe.finish(build_subscribe_message(result))


@like_unsubscribe.handle()
async def handle_like_unsubscribe(event: MessageEvent):
    """处理取消订阅命令。"""

    result = handle_unsubscribe(event.user_id)
    await like_unsubscribe.finish(build_unsubscribe_message(result))


@like_status.handle()
async def handle_like_status(event: MessageEvent):
    """处理订阅状态查询命令。"""

    result = handle_subscription_status(
        event.user_id,
        is_superuser(event.user_id),
    )
    await like_status.finish(build_status_message(result))
