"""消息触发器。"""

from nonebot import on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from .service import send_like_until_limit

like_me = on_fullmatch("赞我", priority=5, block=True)


@like_me.handle()
async def handle_like_me(bot: Bot, event: MessageEvent):
    """处理“赞我”命令。"""

    total = await send_like_until_limit(bot, event.user_id)

    if total > 0:
        await like_me.finish(f"👍 已经给你点了 {total} 个赞")

    await like_me.finish("🌟 今天赞不了你更多了喵~")
