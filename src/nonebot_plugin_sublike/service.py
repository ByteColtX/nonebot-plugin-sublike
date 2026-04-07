"""点赞业务逻辑。"""

from datetime import datetime

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot

from .config import plugin_config
from .models import LikeResult, LikeSource, UserLikeStats
from .store import get_user_stats, upsert_user_stats
from .utils import is_friend


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
