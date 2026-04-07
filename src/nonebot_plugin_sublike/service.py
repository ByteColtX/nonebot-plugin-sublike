"""点赞业务逻辑。"""

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot

from .config import plugin_config
from .utils import is_friend


async def check_instant_like_friend(bot: Bot, user_id: int) -> bool:
    """按配置判断即时点赞是否需要好友关系。"""

    if not plugin_config.sublike_need_friend_me:
        return True

    return await is_friend(bot, user_id)


async def send_like_until_limit(bot: Bot, user_id: int) -> int:
    """持续点赞，直到接口拒绝继续点赞为止。"""

    total = 0
    like_times = plugin_config.sublike_like_times

    while True:
        try:
            result = await bot.send_like(user_id=user_id, times=like_times)
        except Exception as exception:
            if total > 0:
                logger.info(
                    f"用户 {user_id} 点赞已到上限，本次累计 {total} 赞："
                    f"{exception!r}"
                )
            else:
                logger.warning(f"用户 {user_id} 点赞失败：{exception!r}")
            break

        # OneBot v11 单次最多 10 赞，这里按配置值持续累加直到接口拒绝。
        total += like_times

        if isinstance(result, dict):
            if result.get("ok") is False:
                logger.info(f"用户 {user_id} 的点赞接口返回停止信号")
                break
            if result.get("times") == 0:
                logger.info(f"用户 {user_id} 当日剩余点赞次数为 0")
                break

    return total
