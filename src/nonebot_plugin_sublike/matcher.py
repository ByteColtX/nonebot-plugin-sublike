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
from .models import LikeSource
from .service import handle_instant_like

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
        plain_text.startswith(keyword)
        for keyword in plugin_config.sublike_cmd_other
    )


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


like_me = on_message(rule=Rule(is_like_me), priority=5, block=True)
like_other = on_message(rule=Rule(is_like_other), priority=5, block=True)


@like_me.handle()
async def handle_like_me(bot: Bot, event: MessageEvent):
    """处理“赞我”命令。"""

    result = await handle_instant_like(bot, event.user_id)
    await like_me.finish(result.message)


@like_other.handle()
async def handle_like_other(bot: Bot, event: GroupMessageEvent):
    """处理“赞他人”命令。"""

    target_user_id = extract_target_user_id(event)
    if target_user_id is None:
        await like_other.finish("🤡 请提供有效的 QQ 号或 @目标用户")

    result = await handle_instant_like(
        bot,
        target_user_id,
        source=LikeSource.INSTANT,
    )
    if not result.is_friend:
        reply = Message(
            [
                MessageSegment.text("⚠️ 请先让 "),
                MessageSegment.at(target_user_id),
                MessageSegment.text(" 添加机器人为好友后再点赞"),
            ]
        )
        await like_other.finish(reply)

    if result.success:
        reply = Message(
            [
                MessageSegment.text("👍 已经给 "),
                MessageSegment.at(target_user_id),
                MessageSegment.text(f" 点了 {result.total} 个赞"),
            ]
        )
        await like_other.finish(reply)

    reply = Message(
        [
            MessageSegment.text("🌟 今天赞不了 "),
            MessageSegment.at(target_user_id),
            MessageSegment.text(" 更多了喵~"),
        ]
    )
    await like_other.finish(reply)
